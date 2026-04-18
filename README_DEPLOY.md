# NPGC Smart Assistant Deployment Guide

Follow these steps to host your chatbot on Render using the GitHub repo you created.

## Step 1: Push Code to GitHub
Run these commands in your terminal (inside the `chatbot second version` folder):

```bash
git init
git add .
git commit -m "Final production prep for Render"
git branch -M main
git remote add origin https://github.com/Pushpeaks/npgc_rule_based_bot.git
git push -u origin main
```

## Step 2: Deploy on Render
1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository (`npgc_rule_based_bot`).
4. **Settings:**
   - **Name**: `npgc-smart-assistant`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Step 3: Add Environment Variables
This is the **most important** step. In your Render Dashboard, go to the **Environment** tab and add these keys from your `.env` file:

- `GROQ_API_KEY`: (Your key)
- `TIDB_HOST`: `gateway01.ap-southeast-1.prod.aws.tidbcloud.com`
- `TIDB_USER`: `v4ju4BVVA6XzrHr.root`
- `TIDB_PORT`: `4000`
- `TIDB_DB`: `test`
- `TIDB_PASSWORD`: (Your generated password)
- `TIDB_CA_PATH`: `isrgrootx1.pem`

## Step 4: Verify
Once Render finishes building (it takes ~2-3 minutes), click the link it gives you. Your chatbot should be live!

---
**Note:** Your `.env` and individual test scripts were NOT uploaded to GitHub for security. Only the core app files were pushed.
