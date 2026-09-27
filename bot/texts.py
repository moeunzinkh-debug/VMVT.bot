"""All user-facing strings (Khmer) in one place, so translations stay easy."""

from __future__ import annotations

from .services.providers.base import MediaResult
from .utils.formatting import build_caption

# ---------------------------------------------------------------- start ---
WELCOME = (
    "👋 សូមស្វាគមន៍មកកាន់ <b>VMVT.bot</b>\n"
    "\n"
    "🤖 ខ្ញុំអាចជួយអ្នក <b>ទាញយកវីដេអូ TikTok</b> "
    "ដោយ<b>គ្មាន Watermark</b> ដោយឥតគិតថ្លៃ។\n"
    "\n"
    "📥 <b>របៀបប្រើ</b>\n"
    "គ្រាន់តែផ្ញើតំណ TikTok មកឱ្យខ្ញុំ៖\n"
    "• <code>https://vm.tiktok.com/ZMhvzrfeR/</code>\n"
    "• <code>https://vt.tiktok.com/ZSjxxxxx/</code>\n"
    "• <code>https://www.tiktok.com/@user/video/1234567890123456789</code>\n"
    "\n"
    "📌 <b>ពាក្យបញ្ជា</b>\n"
    "/help — របៀបប្រើប្រាស់\n"
    "/about — អំពី Bot នេះ\n"
    "\n"
    "✨ គាំទ្រទាំងវីដេអូខ្លី បណ្ដុំរូបភាព (Slideshow) និង Drama Short"
)

HELP = (
    "📖 <b>របៀបប្រើប្រាស់</b>\n"
    "\n"
    "1️⃣ ចម្លងតំណ TikTok (Share → Copy link)\n"
    "2️⃣ ផ្ញើតំណនោះមកក្នុងទីនេះ\n"
    "3️⃣ រង់ចាំបន្តិច ខ្ញុំនឹងផ្ញើវីដេអូគ្មាន Watermark ត្រឡប់មកវិញ\n"
    "\n"
    "🔗 <b>តំណដែលគាំទ្រ</b>\n"
    "• <code>vt.tiktok.com/…</code> (តំណខ្លី)\n"
    "• <code>vm.tiktok.com/…</code> (តំណខ្លី)\n"
    "• <code>www.tiktok.com/@user/video/…</code> (តំណពេញ)\n"
    "\n"
    "❓ <b>បញ្ហាដែលជួបញឹកញាប់</b>\n"
    "• វីដេអូឯកជន ឬត្រូវបានលុប → មិនអាចទាញយកបានទេ\n"
    "• វីដេអូធំជាង ៥០ MB → ខ្ញុំនឹងផ្ញើតំណទាញយកផ្ទាល់ជំនួស\n"
    "• សេវាកម្មមមាញឹក → សូមរង់ចាំបន្តិច ហើយសាកល្បងម្តងទៀត\n"
    "\n"
    "💬 ពាក្យបញ្ជាផ្សេងទៀត៖ /about"
)

ABOUT = (
    "ℹ️ <b>អំពី VMVT.bot</b>\n"
    "\n"
    "• ទាញយកវីដេអូ TikTok <b>គ្មាន Watermark</b>\n"
    "• គាំទ្រតំណខ្លី <code>vt.tiktok.com</code> និង <code>vm.tiktok.com</code>\n"
    "• គាំទ្រតំណពេញ <code>www.tiktok.com</code>\n"
    "• គុណភាព <b>HD</b> នៅពេលមាន\n"
    "• <b>ឥតគិតថ្លៃ ១០០%</b> មិនត្រូវការគណនី TikTok\n"
    "• ដំណើរការលើ <b>Render Free Plan</b>\n"
    "• មិនរក្សាទុកវីដេអូរបស់អ្នកឡើយ\n"
    "\n"
    "🧰 បច្ចេកវិទ្យា៖ Python • python-telegram-bot • TikWM • yt-dlp"
)

# ------------------------------------------------------------- statuses ---
NO_LINK_HINT = (
    "🤔 ខ្ញុំមិនឃើញតំណ TikTok ទេ។\n"
    "សូមផ្ញើតំណដូចជា <code>https://vm.tiktok.com/ZMhvzrfeR/</code> មកឱ្យខ្ញុំ។\n"
    "វាយ /help ដើម្បីមើលរបៀបប្រើ។"
)

STATUS_RESOLVING = "🔎 កំពុងពិនិត្យតំណ…"
STATUS_DOWNLOADING = "⏬ កំពុងទាញយកវីដេអូ…"
STATUS_UPLOADING = "📤 កំពុងផ្ញើទៅ Telegram…"
STATUS_DONE = "✅ រួចរាល់!"

# --------------------------------------------------------------- errors ---
ERR_GENERIC = "❌ មានបញ្ហាកើតឡើង។ សូមសាកល្បងម្តងទៀត។"
ERR_NOT_FOUND = (
    "😕 <b>រកមិនឃើញវីដេអូនេះទេ</b>\n"
    "មូលហេតុអាចមកពី៖\n"
    "• តំណមិនត្រឹមត្រូវ\n"
    "• វីដេអូជាឯកជន ឬត្រូវបានលុប\n"
    "• ម្ចាស់វីដេអូបានដាក់កម្រិតការទាញយក"
)
ERR_PROVIDERS_DOWN = "🔧 សេវាកម្មទាញយកកំពុងមានបញ្ហា។ សូមសាកល្បងម្តងទៀតក្នុងរយៈពេលបន្តិច។"
ERR_UPLOAD_FAILED = "📤 មិនអាចផ្ញើវីដេអូទៅ Telegram បានទេ។ សូមសាកល្បងម្តងទៀត។"
ERR_EMPTY_MEDIA = "📭 មិនមានឯកសារវីដេអូ ឬរូបភាពនៅក្នុងតំណនេះទេ។"

ERR_TOO_LARGE = (
    "📦 <b>វីដេអូធំពេក</b>\nTelegram អនុញ្ញាតត្រឹម ៥០ MB សម្រាប់ Bot។\nខ្ញុំនឹងព្យាយាមផ្ញើតំណទាញយកផ្ទាល់ជំនួសវិញ…"
)

FALLBACK_LINK_TEXT = (
    "🔗 <b>តំណទាញយកផ្ទាល់</b>\n"
    "ចុចប៊ូតុងខាងក្រោមដើម្បីទាញយកវីដេអូនេះ (គ្មាន Watermark)។\n"
    "⚠️ តំណនេះអាចផុតកំណត់ក្នុងរយៈពេលខ្លី សូមទាញយកភ្លាមៗ។"
)


def rate_limit_message(seconds: float) -> str:
    """Message shown when a user sends too many links too quickly."""
    return f"⏳ <b>សូមបន្ថយល្បឿនបន្តិច</b>\nសូមរង់ចាំ <b>{max(1, round(seconds))}</b> វិនាទី ហើយសាកល្បងម្តងទៀត។"


def slideshow_caption(result: MediaResult, count: int) -> str:
    """Caption used for slideshow (image) posts."""
    return build_caption(result, quality=f"🖼 {count} រូប")


DOWNLOAD_BUTTON = "📥 ទាញយកវីដេអូ"
ORIGINAL_BUTTON = "🎬 មើលដើម"
AUTHOR_BUTTON = "👤 អ្នកនិពន្ធ"
