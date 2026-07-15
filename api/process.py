import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import Response

from navigator_cli import automate_any_month_pdf


app = FastAPI(title="Navigator PDF API")


def _get_api_key() -> str:
    return os.environ.get("NAVIGATOR_API_KEY", "")


def _verify_api_key(x_api_key: str | None) -> None:
    expected_key = _get_api_key()
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/")
def healthcheck():
    return {"status": "ok"}


@app.post("/process")
async def process_pdf(file: UploadFile = File(...), x_api_key: str | None = Header(default=None)):
    _verify_api_key(x_api_key)

    filename = getattr(file, "filename", "input.pdf")
    pdf_bytes = await file.read()
    suffix = Path(filename).suffix or ".pdf"

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / f"input{suffix}"
        output_path = Path(temp_dir) / "output.pdf"

        input_path.write_bytes(pdf_bytes)

        try:
            automate_any_month_pdf(str(input_path), str(output_path))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return Response(
            content=output_path.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{Path(filename).stem}_navigated.pdf"'},
        )