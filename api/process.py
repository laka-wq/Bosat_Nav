import base64
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, JSONResponse

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
async def process_pdf(request: Request, x_api_key: str | None = Header(default=None)):
    _verify_api_key(x_api_key)

    payload = await request.json()
    filename = payload.get("filename", "input.pdf")
    content_base64 = payload.get("content_base64", "")

    if not content_base64:
        raise HTTPException(status_code=400, detail="Missing content_base64")

    try:
        pdf_bytes = base64.b64decode(content_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="content_base64 is not valid base64") from exc

    suffix = Path(filename).suffix or ".pdf"

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / f"input{suffix}"
        output_path = Path(temp_dir) / "output.pdf"

        input_path.write_bytes(pdf_bytes)

        try:
            automate_any_month_pdf(str(input_path), str(output_path))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        processed_bytes = output_path.read_bytes()

        return JSONResponse(
            {
                "status": "ok",
                "filename": f"{Path(filename).stem}_navigated.pdf",
                "content_base64": base64.b64encode(processed_bytes).decode("ascii"),
            }
        )


@app.post("/process-file")
async def process_pdf_file(request: Request, x_api_key: str | None = Header(default=None)):
    _verify_api_key(x_api_key)

    form = await request.form()
    upload = form.get("file")

    if upload is None:
        raise HTTPException(status_code=400, detail="Missing file field")

    filename = getattr(upload, "filename", "input.pdf")
    pdf_bytes = await upload.read()
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