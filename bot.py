import os
import logging
import pandas as pd
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("TELEGRAM_CANCER_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("⚠️ TELEGRAM_BOT_TOKEN environment variable not set")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── LOAD DATA ──────────────────────────────────────────────────
top_cancers_df = pd.read_csv("../resources/csv/top_cancers.csv")
if "Unnamed: 0" in top_cancers_df.columns:
    top_cancers_df = top_cancers_df.drop(columns=["Unnamed: 0"])
top_cancers_df["CountryKey"] = top_cancers_df["Country or Territory"].str.strip().str.lower()
top_cancers_df = top_cancers_df.set_index("CountryKey", drop=False)

top_risks_df = pd.read_csv("../resources/csv/top_risks.csv")
if "Unnamed: 0" in top_risks_df.columns:
    top_risks_df = top_risks_df.drop(columns=["Unnamed: 0"])
top_risks_df = top_risks_df.set_index("Cancer Outcome", drop=False)

df = pd.read_json("../resources/json/lifestyle_data.json", lines=True).to_dict(orient="records")
def create_response(keyword):
    """
    Create a response string based on the keyword and JSON data.

    :param keyword: The keyword to search for in the JSON data
    :param json_data: The JSON data containing lifestyle information
    :return: A formatted response string
    """
    response = f"Here is the information related to '{keyword}':\n\n"
    
    filtered_data = [item for item in df if keyword.lower() in item['Agent'].lower()]
    
    if not filtered_data:
        return f"No information found for '{keyword}'."
    
    for item in filtered_data:
        response += f"**Agent:** {item['Agent']}\n"
        response += f"**Group:** {item['Group']}\n"
        response += f"**Evaluation Year:** {item['Evaluation year']}\n"
        response += f"**Description:** {item.get('Description', 'No description available.')}\n\n"
    
    return response.strip()

# ─── ALIASES & NORMALIZATION ─────────────────────────────────────
ALIASES = {
    "usa": "united states of america",
    "us":  "united states of america",
    "u.s.": "united states of america",
    "uk":  "united kingdom of great britain and northern ireland",
    "u.k.": "united kingdom of great britain and northern ireland",
    # …add any others you need…
}

advice_by_risk = {
    "Cancers attributable to infections": (
        "Limit your exposure to direct sunlight and use UV protection if you have to. "
        "Use an air purifier at home, and if you live in a high‐pollution city, check daily AQI forecasts "
        "and stay indoors on ‘very unhealthy’ days."
  ),
    "Smoking prevalence female": (
        "Quitting smoking can cut risk of many cancers by 30–50% within the first year. "
        "Consider nicotine replacement therapy, join a support group, or speak with your GP about counseling."
    ),
    "Indoor air pollution": (
        "Avoid using open coal or biomass stoves indoors. Improve ventilation by keeping windows open or installing chimneys. "
        "Consider switching to cleaner cookstoves or electric heating if available."
    ),
    "Obesity prevalence male": (
        "Aim to keep your BMI between 18.5 and 24.9 kg/m². "
        "Try to exercise at least 150 minutes/week (e.g. brisk walking), reduce sugary/processed foods, "
        "and speak with a dietitian if you need personalized guidance."
    ),
    "HIV Prevalence (%)": (
       "Practice safe sex practices. Avoid unprotected sex by using condoms correctly and consistently during all sexual activity, getting regularly tested and treated for STIs, limiting the number of sexual partners, do not share injection needles."
)
} 


def normalize_country_input(user_text: str) -> str:
    candidate = user_text.strip().lower()
    return ALIASES.get(candidate, candidate)

def get_cancers_for_country_and_gender(country_row: pd.Series, gender: str) -> list[str]:
    """
    Given a pandas Series for one country row (with columns Top1 Cancer, Top2 Cancer, Top3 Cancer)
    and a gender ("male" or "female"), return a prioritized list of cancer‐outcome strings.
    """
    gender = gender.strip().lower()
    filtered, fallback = [], []
    for col in ["Top1 Cancer", "Top2 Cancer", "Top3 Cancer"]:
        val = country_row.get(col, "")
        if not isinstance(val, str) or not val.strip():
            continue
        # If the string explicitly contains ", male" or ", female", match it
        if f", {gender}" in val.lower():
            filtered.append(val)
        else:
            fallback.append(val)
    return filtered if filtered else fallback


def get_risk_factors_for_cancer(outcome: str) -> list[str]:
    """
    Given a cancer‐outcome string (e.g. "Lung cancer incidence rates, male"),
    return its Top1 and Top2 Risk Factor as a list. If not found, return [].
    """
    try:
        row = top_risks_df.loc[outcome]
        factors = []
        for col in ["Top1 Risk Factor", "Top2 Risk Factor"]:
            val = row.get(col, "")
            if isinstance(val, str) and val.strip():
                factors.append(val)
        return factors
    except KeyError:
        return []

# ─── STATE + HANDLERS ────────────────────────────────────────────
user_state = {}  # chat_id → {"country": str, "gender": str}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 Hello! I’m *CancerInfo_by_NeuroNexus_bot*.\n\n"
        "I can provide you with evidence-based lifestyle recommendations to help reduce cancer risk.\n\n"
        "Use /help to see what I can do."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "*Available Commands:*\n\n"
        "/start – Greet and explain what I do\n"
        "/help  – Show this help message\n"
        "/recommendation – Health advise based on demographics\n"
        "/risk – Information about common cancerogenic hazards\n"
        "_Example:_ `/recommendation`"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def recommendation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_state.pop(chat_id, None)
    await update.message.reply_text(
        "👋 Welcome! I can give you the top cancer risks and advice based on your country and gender.\n"
        "First, please type your country (e.g., \"France\", \"Brazil\", \"India\")."
    )

async def risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /risk <keyword> – Looks up the given keyword in lifestyle_data.json and returns the matching entries.
    If no keyword is provided, prompt the user for correct usage.
    """
    chat_id = update.effective_chat.id
    args = context.args  # list of words after “/risk”

    if not args:
        await update.message.reply_text(
            "❗️ Usage: /risk <keyword>\n"
            "Please provide exactly one keyword (e.g. `/risk Tobacco`)."
        )
        return

    # Join all args into a single search term (in case keyword itself has spaces)
    keyword = " ".join(args).strip()
    response_text = create_response(keyword)

    # Send the response with Markdown formatting (for bold/italics)
    await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Sorry, I didn’t understand that command. Use /help to see what I can do."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if chat_id not in user_state:
        raw = text  # what the user actually typed
        country_key = normalize_country_input(raw)

        # Debug: log the first few index keys so we can see what's available
        if country_key not in top_cancers_df.index:
            logger.info("First 20 country keys: %s", list(top_cancers_df.index)[:20])
            await update.message.reply_text(
                f"Sorry, I don’t recognize “{raw}”. Please send your country exactly as in the list (e.g. \"France\")."
            )
            return

        user_state[chat_id] = {"country": country_key}
        await update.message.reply_text(
            "Great. Now please type your gender (\"male\" or \"female\")."
        )
        return

    # 2) Gender stage
    if "gender" not in user_state[chat_id]:
        gender = text.lower()
        if gender not in ("male", "female"):
            await update.message.reply_text("Please type exactly \"male\" or \"female\".")
            return

        user_state[chat_id]["gender"] = gender

        # We now have both country & gender → build the response
        country_key = user_state[chat_id]["country"]
        country_row = top_cancers_df.loc[country_key]

        # 1) Get the list of cancer outcomes for this country/gender
        cancer_list = get_cancers_for_country_and_gender(country_row, gender)
        if not cancer_list:
            await update.message.reply_text(
                "I couldn’t find any top cancers for your country/gender. Sorry!"
            )
            user_state.pop(chat_id, None)
            return

        # 2) For each cancer, look up risk factors + advice
        reply_lines = []
        for outcome in cancer_list:
            reply_lines.append(f"🔬 *{outcome}*")
            risk_factors = get_risk_factors_for_cancer(outcome)
            if not risk_factors:
                reply_lines.append("  – No risk‐factor data available.\n")
            else:
                for rf in risk_factors:
                    advice_text = advice_by_risk.get(
                        rf,
                        f"  – No specific advice for “{rf}”."
                    )
                    reply_lines.append(f"  • *{rf}*: {advice_text}")
                reply_lines.append("")  # blank line between cancers

        # Send the assembled reply (Markdown formatting)
        await update.message.reply_text(
            "\n".join(reply_lines),
            parse_mode=ParseMode.MARKDOWN
        )

        # Clear state so they can /recommendation again later
        user_state.pop(chat_id, None)
        return


    # Anything else
    await update.message.reply_text("Type /start to begin again.")


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("recommendation", recommendation_command))
    application.add_handler(CommandHandler("risk", risk_command))

    application.add_handler(
        MessageHandler(filters.Regex(r"^/"), unknown_command)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    logger.info("🤖 Bot is starting—polling Telegram for updates...")
    application.run_polling()


if __name__ == "__main__":
    main()
