import logging
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "model-axle.json"
SHEET_NAME = "Expense_Tracker"

creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1


BOT_TOKEN = os.environ["API_KEY"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send me a message like 'spent 200 groceries' or 'added 1000 salary'.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip().lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    match = re.match(r"(spent|added|\+|\-)\s*(\d+)(?:\s+(.*))?", msg)

    if match:
        tx_type_raw, amount, description = match.groups()
        tx_type = "Expense" if tx_type_raw in ["spent", "-"] else "Income"
        description = description if description else "No Description"

        sheet.append_row([now, tx_type, amount, description])

        await update.message.reply_text(f"{tx_type} of ₹{amount} added for '{description}'. ✅")
    else:
        await update.message.reply_text("Please send like 'spent 200 dinner' or 'added 1000 salary'.")

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period = "today"
    if context.args:
        period = context.args[0].lower()

    now = datetime.now()
    rows = sheet.get_all_records()
    
    total_income = 0
    total_expense = 0

    for row in rows:
        try:
            date_str = row['Date']
            entry_date = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
            amount = int(row['Amount'])
            if row['Type'].lower() == "income":
                is_income = True
            else:
                is_income = False

            include = False
            if period == "today":
                include = entry_date.date() == now.date()
            elif period == "week":
                include = (now - timedelta(days=7)).date() <= entry_date.date() <= now.date()
            elif period == "month":
                include = entry_date.month == now.month and entry_date.year == now.year
            elif period == "year":
                include = entry_date.year == now.year

            if include:
                if is_income:
                    total_income += amount
                else:
                    total_expense += amount

        except Exception as e:
            print("Skipping row due to error:", e)
            continue

    balance = total_income - total_expense
    response = (
        f"📊 *Summary for {period.capitalize()}*\n"
        f"Income: ₹{total_income}\n"
        f"Expense: ₹{total_expense}\n"
        f"Balance: ₹{balance}"
    )

    await update.message.reply_text(response, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ * Usage Instructions: *\n"
        "- `spent 200 groceries`\n"
        "- `added 1000 salary`\n"
        "- `+1000 project` or `-300 dinner`\n"
        "- `/summary today | week | month | year`\n",
        parse_mode="Markdown"
    )


# === Bot Setup ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("summary", summary))

print("Bot is running...")
app.run_polling()