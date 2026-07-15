# Navigator PDF automation

This workspace now contains:

- `navigator_cli.py`: the original PDF navigation CLI.
- `api/process.py`: a Vercel-ready FastAPI wrapper around the CLI.
- `wordpress-plugin/navigator-pdf-linker.php`: a WordPress plugin that uploads PDFs to the Vercel API.

## Vercel deployment

1. Push this repo to GitHub.
2. Connect the repo to Vercel.
3. Set `NAVIGATOR_API_KEY` in Vercel environment variables if you want auth.
4. Deploy.

The main endpoint is `POST /process` and accepts a multipart `file` field.

## WordPress setup

1. Copy `wordpress-plugin/navigator-pdf-linker.php` into a plugin folder named `navigator-pdf-linker`.
2. Zip that folder or upload it through the WordPress plugin screen.
3. Activate the plugin.
4. Open Settings and set the Vercel API URL plus the same API key.
5. Add shortcode `[navigator_pdf_upload]` to a page.

## Local testing

Run the Python app locally with your Vercel-style ASGI server of choice, then POST a JSON body to `/process`.