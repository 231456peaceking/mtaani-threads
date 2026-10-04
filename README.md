# Mtaani Threads (Flask + M-PESA Daraja)

```
mtaani-threads/
  app.py              web server + routes + product prices
  daraja.py           Daraja integration (token, STK push, callback parser)
  public/index.html   the shop page
  tools/daraja_test.py  your original Daraja script (standalone test)
  .env                your keys (you create it from .env.example)
```

## First-time setup
```
cd "mtaani threads"           # use quotes if the folder has a space
sudo apt install python3-venv  # only if venv fails
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # then fill in .env
```

## Every time you run it
Terminal 1:  `ngrok http 3000`  -> copy the https link into DARAJA_CALLBACK_URL in .env (keep /api/mpesa/callback at the end)
Terminal 2:  `source venv/bin/activate && python3 app.py`  -> open http://localhost:3000

## Test the Daraja credentials alone
`python3 tools/daraja_test.py`
