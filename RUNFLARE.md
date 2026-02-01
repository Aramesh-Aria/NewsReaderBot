# Deploy NewsReaderBot on Runflare

[Runflare](https://runflare.com/docs/) supports **Python** services. This bot is a long-running process (polling), not a web app.

## Steps

1. **Create a project** on [Runflare](https://runflare.com) and add a **Python** service (not Django/Flask).
2. **Connect your repo** (GitHub/GitLab) or deploy with CLI.
3. **Set start command** in the service settings:
   ```bash
   python main.py
   ```
4. **Set environment variables** in Runflare dashboard:
   - `BOT_TOKEN` – from [BotFather](https://t.me/BotFather)
   - `API_KEY` – from [NewsAPI](https://newsapi.org/)
   - `DATABASE_URL` – e.g. `postgresql://...` if you use Runflare Postgres, or keep SQLite path for default DB.

5. **Database**: For production, attach a **Postgres** database in Runflare and set `DATABASE_URL`. Run migrations after first deploy (e.g. via Runflare shell/CLI):
   ```bash
   python -m alembic upgrade head
   ```

## Requirements

- `requirements.txt` is at the project root (no need for the Runflare package inside the app).
- For **deploying via CLI** from your machine, install the Runflare CLI separately: `pip install runflare`
- Start command: `python main.py`

## Docs

- [Runflare – Python](https://runflare.com/docs/) (شروع به کار → ایجاد پروژه → ایجاد سرویس)
- [Runflare – CLI](https://runflare.com/docs/) (نصب و به روز رسانی CLI، ارسال فایل، مدیریت سرویس)
