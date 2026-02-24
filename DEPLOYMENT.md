# Exhibition Booth Tracker - Deployment Guide

This document outlines the steps to run your Booth Tracker locally, set up the Supabase database, and connect your automated emails.

## 1. Setup Supabase (5 Minutes)
1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **"New Project"**.
3. Once the project is created, navigate to the **SQL Editor** (left menu).
4. **Copy & Paste the contents of `db.sql`** into the editor and hit **Run**.
   - *This creates your `companies`, `notes`, and `attachments` tables, plus the Storage bucket.*
5. Go to **Project Settings -> API**.
6. Find your Project URL and anon/public `anon key`.

## 2. Connect Your App Locally
1. In the `fuar` folder, create a new file named `.env`.
2. Add your Supabase credentials to `.env`:
   ```env
   SUPABASE_URL=your-project-url-here
   SUPABASE_KEY=your-anon-key-here
   ```
3. Run the database seed script to import all 1600+ companies from your CSV:
   ```bash
   python seed_database.py
   ```
4. Start the Streamlit App:
   ```bash
   streamlit run app.py
   ```
   *The app will instantly open in your browser at `http://localhost:8501:8501/`.*

## 3. Web Deployment (Free via Streamlit Cloud)
To let your team use the app:
1. Push your `fuar` folder to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and link your GitHub.
3. Select `app.py` as the main file.
4. **Crucial:** In Streamlit Cloud settings, go to **Advanced Settings -> Secrets** and paste your `.env` variables there securely.

## 4. Setting up the Automated Email Webhook (Zero Code)
*(If you want to use Zapier instead of hosting `email_webhook.py` on a server)*
1. Go to [zapier.com](https://zapier.com/app/dashboard).
2. Create a Zap triggered by **Email Parser by Zapier** (gives you a custom secret email address).
3. Set the Action to **PostgreSQL**.
4. Use your Supabase Database credentials to connect.
5. Action: **Insert Row**.
   - Table: `notes`
   - Content: Extract the email Body from step 1.
   - Company ID: *We can set up a "Find Row" step to search the `companies` table based on the sender's domain!*
