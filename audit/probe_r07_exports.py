"""Fault injection for export recovery; extracted functions and temporary files only."""
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


def run_case(case):
    source = Path(__file__).resolve().parents[1] / "scripts" / "bot_server.py"
    names = {"atomic_write_csv", "atomic_write_excel", "save_session_csv_and_excel",
             "export_session_csv", "export_session_excel"}
    nodes = []
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            nodes.append(node)
    with tempfile.TemporaryDirectory(prefix="r07-synthetic-") as temp:
        ns = dict(os=os, tempfile=tempfile, csv=csv, urllib=urllib, json=json, time=time,
                  List=List, Dict=Dict, Any=Any, Optional=Optional, HTTPException=HTTPException,
                  FileResponse=FileResponse, __file__=str(Path(temp) / "scripts" / "bot_server.py"),
                  EXPORTS_DIR=str(Path(temp) / "exports"),
                  state=SimpleNamespace(session_id="fixture"),
                  SESSION_ID_REGEX=re.compile(r"^[a-zA-Z0-9_-]{1,64}$"),
                  RESERVED_SESSION_ALIASES=frozenset({"latest"}),
                  get_effective_portal_url=lambda: "https://portal.example.invalid")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), ns)
        save = ns["save_session_csv_and_excel"]
        save([{"email": "generation-a@example.invalid", "pin": "fixture-a"}], "fixture")
        csv_path = Path(ns["EXPORTS_DIR"]) / "muse_session_fixture.csv"
        excel_path = csv_path.with_suffix(".xlsx")
        old_csv, old_excel = csv_path.read_bytes(), excel_path.read_bytes()
        real_excel, real_replace, real_open = ns["atomic_write_excel"], os.replace, builtins.open

        def fail_excel(path, wb):
            if str(path) == str(excel_path):
                raise OSError("synthetic Excel failure")
            return real_excel(path, wb)

        def replace(src, dst):
            if case in {"restore_failure", "marker_and_restore_failure"} and ".bak_" in str(src):
                raise PermissionError("synthetic restore failure")
            return real_replace(src, dst)

        def open_file(file, mode="r", *args, **kwargs):
            if case == "marker_and_restore_failure" and str(file).endswith(".failed") and "w" in mode:
                raise PermissionError("synthetic marker failure")
            return real_open(file, mode, *args, **kwargs)

        ns["atomic_write_excel"] = fail_excel
        ns["open"] = open_file
        with patch.object(os, "replace", side_effect=replace):
            if case == "backup_failure":
                with patch.object(shutil, "copy2", side_effect=PermissionError("synthetic backup failure")):
                    try:
                        save([{"email": "generation-b@example.invalid", "pin": "fixture-b"}], "fixture")
                    except OSError:
                        pass
            else:
                try:
                    save([{"email": "generation-b@example.invalid", "pin": "fixture-b"}], "fixture")
                except OSError:
                    pass
        statuses = {}
        for kind in ("csv", "excel"):
            try:
                statuses[kind] = asyncio.run(ns["export_session_" + kind]("fixture")).status_code
            except HTTPException as exc:
                statuses[kind] = exc.status_code
        print(json.dumps({"case": case, "statuses": statuses,
                          "old_csv_preserved": csv_path.exists() and csv_path.read_bytes() == old_csv,
                          "old_excel_preserved": excel_path.exists() and excel_path.read_bytes() == old_excel,
                          "backup_files_remaining": len(list(Path(temp).rglob("*.bak_*"))),
                          "csv_contains_generation_b": csv_path.exists() and b"generation-b@" in csv_path.read_bytes()}))


if __name__ == "__main__":
    for case_name in ("backup_failure", "restore_failure", "marker_and_restore_failure"):
        run_case(case_name)
