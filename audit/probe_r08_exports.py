"""Fault injection for R08 export lifecycle and commit point verification; extracted functions and temporary files only."""
import ast
import asyncio
import builtins
import csv
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import FileResponse


def get_extracted_ns(temp_dir: str):
    source = Path(__file__).resolve().parents[1] / "scripts" / "bot_server.py"
    names = {"atomic_write_csv", "atomic_write_excel", "save_session_csv_and_excel",
             "export_session_csv", "export_session_excel"}
    nodes = []
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            nodes.append(node)
    ns = dict(os=os, tempfile=tempfile, csv=csv, urllib=urllib, json=json, time=time,
              List=List, Dict=Dict, Any=Any, Optional=Optional, HTTPException=HTTPException,
              FileResponse=FileResponse, __file__=str(Path(temp_dir) / "scripts" / "bot_server.py"),
              EXPORTS_DIR=str(Path(temp_dir) / "exports"),
              ROOT_DIR=str(Path(temp_dir)),
              state=SimpleNamespace(session_id="fixture"),
              SESSION_ID_REGEX=re.compile(r"^[a-zA-Z0-9_-]{1,64}$"),
              RESERVED_SESSION_ALIASES=frozenset({"latest"}),
              get_effective_portal_url=lambda: "https://portal.example.invalid")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), ns)
    return ns


def run_case_pending_clear_existing_generation():
    with tempfile.TemporaryDirectory(prefix="r08-pending-clear-") as temp:
        ns = get_extracted_ns(temp)
        save = ns["save_session_csv_and_excel"]
        save([{"email": "generation-a@example.invalid", "pin": "fixture-a"}], "fixture")
        csv_path = Path(ns["EXPORTS_DIR"]) / "muse_session_fixture.csv"
        excel_path = csv_path.with_suffix(".xlsx")
        old_csv, old_excel = csv_path.read_bytes(), excel_path.read_bytes()

        real_remove = os.remove
        def remove_fail_pending(p):
            if str(p).endswith(".pending"):
                raise PermissionError("synthetic pending clear failure")
            return real_remove(p)

        writer_success = True
        try:
            with patch.object(os, "remove", side_effect=remove_fail_pending):
                save([{"email": "generation-b@example.invalid", "pin": "fixture-b"}], "fixture")
        except OSError:
            writer_success = False

        statuses = {}
        for kind in ("csv", "excel"):
            try:
                statuses[kind] = asyncio.run(ns["export_session_" + kind]("fixture")).status_code
            except HTTPException as exc:
                statuses[kind] = exc.status_code

        backup_files = list(Path(temp).rglob("*.bak_*"))
        result = {
            "case": "pending_clear_existing_generation",
            "writer_success": writer_success,
            "statuses": statuses,
            "old_csv_preserved": csv_path.exists() and csv_path.read_bytes() == old_csv,
            "old_excel_preserved": excel_path.exists() and excel_path.read_bytes() == old_excel,
            "recoverable_backup_count": len(backup_files),
        }
        print(json.dumps(result))
        assert writer_success is False, "Writer must report failure when pending clear fails"
        assert statuses == {"csv": 409, "excel": 409}, f"Endpoints must return 409, got {statuses}"
        assert result["old_csv_preserved"] or result["recoverable_backup_count"] > 0, "Gen A must be preserved or recoverable"


def run_case_failed_clear_writer_success():
    with tempfile.TemporaryDirectory(prefix="r08-failed-clear-") as temp:
        ns = get_extracted_ns(temp)
        save = ns["save_session_csv_and_excel"]
        # Seed pre-existing failed marker
        failed_marker = Path(ns["EXPORTS_DIR"]) / "muse_session_fixture.failed"
        failed_marker.parent.mkdir(parents=True, exist_ok=True)
        failed_marker.write_text(json.dumps({"error": "old failure"}), encoding="utf-8")

        real_remove = os.remove
        def remove_fail_failed(p):
            if str(p).endswith(".failed"):
                raise PermissionError("synthetic failed marker unlink error")
            return real_remove(p)

        writer_success = True
        try:
            with patch.object(os, "remove", side_effect=remove_fail_failed):
                save([{"email": "generation-b@example.invalid", "pin": "fixture-b"}], "fixture")
        except OSError:
            writer_success = False

        statuses = {}
        for kind in ("csv", "excel"):
            try:
                statuses[kind] = asyncio.run(ns["export_session_" + kind]("fixture")).status_code
            except HTTPException as exc:
                statuses[kind] = exc.status_code

        result = {
            "case": "failed_clear_writer_failure_agrees_with_endpoint",
            "writer_success": writer_success,
            "statuses": statuses,
        }
        print(json.dumps(result))
        assert writer_success is False, "Writer must fail when failure marker cannot be unlinked"
        assert statuses == {"csv": 409, "excel": 409}, f"Endpoints must reject with 409 while .failed exists"

        # Now test recovery retry without unlink error
        retry_success = False
        try:
            save([{"email": "generation-b@example.invalid", "pin": "fixture-b"}], "fixture")
            retry_success = True
        except OSError:
            retry_success = False

        retry_statuses = {}
        for kind in ("csv", "excel"):
            try:
                retry_statuses[kind] = asyncio.run(ns["export_session_" + kind]("fixture")).status_code
            except HTTPException as exc:
                retry_statuses[kind] = exc.status_code

        retry_result = {
            "case": "failed_clear_recovery_success",
            "writer_success": retry_success,
            "statuses": retry_statuses,
        }
        print(json.dumps(retry_result))
        assert retry_success is True, "Recovery export must succeed"
        assert retry_statuses == {"csv": 200, "excel": 200}, f"Endpoints must serve 200 after recovery, got {retry_statuses}"


def run_case_post_commit_backup_cleanup_failure():
    with tempfile.TemporaryDirectory(prefix="r08-post-commit-") as temp:
        ns = get_extracted_ns(temp)
        save = ns["save_session_csv_and_excel"]
        save([{"email": "generation-a@example.invalid", "pin": "fixture-a"}], "fixture")

        real_remove = os.remove
        def remove_fail_backup(p):
            if ".bak_" in str(p):
                raise PermissionError("synthetic post-commit backup unlink error")
            return real_remove(p)

        writer_success = False
        try:
            with patch.object(os, "remove", side_effect=remove_fail_backup):
                save([{"email": "generation-b@example.invalid", "pin": "fixture-b"}], "fixture")
            writer_success = True
        except OSError:
            writer_success = False

        statuses = {}
        for kind in ("csv", "excel"):
            try:
                statuses[kind] = asyncio.run(ns["export_session_" + kind]("fixture")).status_code
            except HTTPException as exc:
                statuses[kind] = exc.status_code

        csv_path = Path(ns["EXPORTS_DIR"]) / "muse_session_fixture.csv"
        csv_text = csv_path.read_text(encoding="utf-8") if csv_path.exists() else ""

        result = {
            "case": "post_commit_backup_cleanup_failure",
            "writer_success": writer_success,
            "statuses": statuses,
            "committed_generation_b_served": "generation-b@" in csv_text,
        }
        print(json.dumps(result))
        assert writer_success is True, "Post-commit backup cleanup failure must not fail the export"
        assert statuses == {"csv": 200, "excel": 200}, f"Endpoints must serve committed generation, got {statuses}"
        assert result["committed_generation_b_served"], "Committed generation B must be served"


if __name__ == "__main__":
    run_case_pending_clear_existing_generation()
    run_case_failed_clear_writer_success()
    run_case_post_commit_backup_cleanup_failure()
