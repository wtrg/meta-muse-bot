"""Offline R06 probes: AST-extracted source, synthetic data, temporary files only."""
import ast
import asyncio
import csv
import json
import os
import re
import tempfile
import time
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse


def main():
    source = Path(__file__).resolve().parents[1] / "scripts" / "bot_server.py"
    names = {"atomic_write_text", "atomic_write_csv", "atomic_write_excel",
             "save_session_csv_and_excel", "export_session_csv",
             "export_session_excel", "save_accounts"}
    selected = []
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            selected.append(node)
    with tempfile.TemporaryDirectory(prefix="r06-export-synthetic-") as temp:
        ns = dict(os=os, tempfile=tempfile, csv=csv, urllib=urllib, json=json,
                  time=time, List=List, Dict=Dict, Any=Any, Optional=Optional,
                  HTTPException=HTTPException, FileResponse=FileResponse,
                  __file__=str(Path(temp) / "scripts" / "bot_server.py"),
                  EXPORTS_DIR=str(Path(temp) / "exports"),
                  state=SimpleNamespace(session_id="fixture_session", accounts=[]),
                  SESSION_ID_REGEX=re.compile(r"^[a-zA-Z0-9_-]{1,64}$"),
                  RESERVED_SESSION_ALIASES=frozenset({"latest", "current", "default", "all", "null", "undefined"}),
                  get_effective_portal_url=lambda: "https://portal.example.invalid")
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), ns)
        ns["save_session_csv_and_excel"](
            [{"email": "old@example.invalid", "pin": "fixture-old"}], "fixture_session")
        excel_path = Path(ns["EXPORTS_DIR"]) / "muse_session_fixture_session.xlsx"
        old_bytes = excel_path.read_bytes()
        real_writer = ns["atomic_write_excel"]

        def fail_excel(path, wb):
            if path == str(excel_path):
                raise OSError("synthetic disk failure")
            return real_writer(path, wb)

        ns["atomic_write_excel"] = fail_excel
        try:
            ns["save_session_csv_and_excel"](
                [{"email": "new@example.invalid", "pin": "fixture-new"}], "fixture_session")
        except OSError:
            pass
        outcome = {}
        for kind in ("csv", "excel"):
            try:
                result = asyncio.run(ns["export_session_" + kind]("fixture_session"))
                outcome[kind] = {"status": result.status_code,
                                 "old_bytes_returned": Path(result.path).read_bytes() == old_bytes}
            except HTTPException as exc:
                outcome[kind] = {"status": exc.status_code}
        print(json.dumps({"finding": "R06_EXISTING_SESSION_EXCEL_FAILURE", "result": outcome}))
        ns["ACCOUNTS_FILE"] = str(Path(temp) / "synthetic_accounts.json")

        def fail_txt():
            raise OSError("synthetic TXT failure")

        ns["save_accounts_txt"] = fail_txt
        ns["print"] = lambda *args, **kwargs: None
        try:
            ns["save_accounts"]()
            propagated = False
        except OSError:
            propagated = True
        print(json.dumps({"finding": "R06_TXT_CALLER_FAILURE", "exception_propagated": propagated}))


if __name__ == "__main__":
    main()
