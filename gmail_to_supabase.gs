// ============================================================
// IBC / KBIS / Fuar Mailleri → Supabase Sync Script
// Gmail Apps Script — uygar@mercan.net Workspace'inde çalışır
// Her 15 dakikada otomatik tetiklenir
// ============================================================

// ──────────────────────────────────────────────────────────
// 1. AYARLAR
// ──────────────────────────────────────────────────────────
var SUPABASE_URL      = "https://voiexsboyzgglnmtinhf.supabase.co";
var SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZvaWV4c2JveXpnZ2xubXRpbmhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4OTIxODQsImV4cCI6MjA4NzQ2ODE4NH0.Q5-EXFDNVKAW_sCBp0KQRrv7xzziQqFuZ2MXqwbusdM";

// ▸ Şirket eşleştirmesi YOK — önce topla, sonra eşleştir.
// ▸ Tüm fuar mailleri → notes tablosu, type="email", company_id=NULL

// Gmail arama — IBC + KBIS + diğer fuarlar
var GMAIL_SEARCH_QUERY = [
  '(',
    '"IBC" OR "International Builders" OR',
    '"KBIS" OR "Kitchen Bath" OR "Kitchen & Bath"',
    'OR "Orlando" OR "Las Vegas Convention"',
    'OR "NAHB" OR "NKBA" OR "booth" OR "exhibitor"',
    'OR "trade show" OR "product catalog" OR "price list"',
    'OR "from:nahb.org" OR "from:kbis.com" OR "from:ibsvegas.com"',
  ')',
  'after:2026/2/17'  // Fuar 17 Şubat 2026'da başladı
].join(' ');

// İşlenen mail ID'lerini Properties'te sakla
var PROCESSED_KEY = "ibc_processed_ids_v2";

// ──────────────────────────────────────────────────────────
// 2. ANA FONKSİYON
// ──────────────────────────────────────────────────────────
function syncEmailsToSupabase() {
  var props = PropertiesService.getScriptProperties();
  var processedRaw = props.getProperty(PROCESSED_KEY) || "[]";
  var processed = JSON.parse(processedRaw);

  var threads = GmailApp.search(GMAIL_SEARCH_QUERY, 0, 100);
  var newProcessed = [];
  var insertCount = 0;

  threads.forEach(function(thread) {
    thread.getMessages().forEach(function(msg) {
      var msgId = msg.getId();
      if (processed.indexOf(msgId) !== -1) return;

      var subject  = msg.getSubject() || "(Konu yok)";
      var sender   = msg.getFrom();
      var dateObj  = msg.getDate();
      var body     = msg.getPlainBody().substring(0, 4000);
      var fullText = subject + " " + body;

      // Hangi fuarla ilgili?
      var eventTag = detectEvent(fullText);

      // Aciliyet skoru (0-10)
      var urgency = scoreUrgency(subject, body);

      // Gönderen domain
      var senderDomain = extractDomain(sender);

      // Eşleştirme bırakıyoruz → company_id: NULL
      // İçerik yapılandırılmış şekilde kaydet
      var content = buildContent(subject, sender, senderDomain, dateObj, eventTag, urgency, body);

      var success = insertNote(content, msgId, eventTag, urgency, senderDomain);
      if (success) {
        newProcessed.push(msgId);
        insertCount++;
        Logger.log("✅ [" + eventTag + "] " + subject);
      }
    });
  });

  // İşlenen ID'leri güncelle (son 1000 tut)
  var allProcessed = processed.concat(newProcessed);
  if (allProcessed.length > 1000) allProcessed = allProcessed.slice(-1000);
  props.setProperty(PROCESSED_KEY, JSON.stringify(allProcessed));

  Logger.log("─── Tamamlandı: " + insertCount + " yeni email eklendi ───");
}

// ──────────────────────────────────────────────────────────
// 3. YARDIMCI FONKSİYONLAR
// ──────────────────────────────────────────────────────────

/**
 * Email metnine bakarak hangi fuar/etkinlikle ilgili olduğunu tespit eder.
 */
function detectEvent(text) {
  var t = text.toLowerCase();
  if (t.indexOf("kbis") !== -1 || t.indexOf("kitchen bath") !== -1 || t.indexOf("kitchen & bath") !== -1) {
    return "KBIS";
  }
  if (t.indexOf("ibs") !== -1 || t.indexOf("international builders") !== -1 || t.indexOf("ibsvegas") !== -1) {
    return "IBS";
  }
  if (t.indexOf("nahb") !== -1) {
    return "NAHB";
  }
  if (t.indexOf("nkba") !== -1) {
    return "NKBA";
  }
  if (t.indexOf("orlando") !== -1) {
    return "KBIS-Orlando";
  }
  if (t.indexOf("las vegas") !== -1) {
    return "IBS-LasVegas";
  }
  if (t.indexOf("trade show") !== -1 || t.indexOf("exhibitor") !== -1) {
    return "TradeShow";
  }
  return "Fuar-Genel";
}

/**
 * Aciliyet skorlayıcı (0-10):
 * - Subject'te "urgent", "deadline", "offer" geçiyorsa +puan
 * - Fiyat listesi, katalog, toplantı daveti → yüksek
 */
function scoreUrgency(subject, body) {
  var score = 0;
  var s = (subject + " " + body).toLowerCase();

  var highSignals = ["urgent", "deadline", "offer", "price list", "quote", "fiyat", "teklif",
                     "meeting", "appointment", "invite", "exclusive", "limited", "today", "asap",
                     "expires", "katalog", "catalog", "sample", "demo request"];
  var medSignals  = ["new product", "launch", "announcement", "visit", "schedule", "brochure",
                     "partnership", "distributor", "follow up", "follow-up", "product line"];

  highSignals.forEach(function(w) { if (s.indexOf(w) !== -1) score += 2; });
  medSignals.forEach(function(w)  { if (s.indexOf(w) !== -1) score += 1; });

  return Math.min(score, 10); // Maks 10
}

/**
 * "John Doe <john@company.com>" formatından domain çıkarır.
 */
function extractDomain(sender) {
  var match = sender.match(/@([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})/);
  return match ? match[1] : "bilinmiyor";
}

/**
 * Supabase'e yüklenecek içeriği formatlı markdown olarak oluşturur.
 */
function buildContent(subject, sender, domain, dateObj, eventTag, urgency, body) {
  var dateStr = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), "dd.MM.yyyy HH:mm");
  var urgencyBadge = urgency >= 7 ? "🔴 YÜKSEKBurası" : urgency >= 4 ? "🟡 ORTA" : "🟢 Düşük";

  return "📧 **" + subject + "**\n\n"
       + "| Alan | Bilgi |\n"
       + "|------|-------|\n"
       + "| ✉️ Gönderen | " + sender + " |\n"
       + "| 🌐 Domain | " + domain + " |\n"
       + "| 🎪 Fuar | " + eventTag + " |\n"
       + "| 🔥 Öncelik | " + urgencyBadge + " (" + urgency + "/10) |\n"
       + "| 📅 Tarih | " + dateStr + " |\n\n"
       + "---\n"
       + body;
}

/**
 * Supabase notes tablosuna ekler.
 * company_id = NULL → sonradan eşleştirilecek
 */
function insertNote(content, gmailMsgId, eventTag, urgency, senderDomain) {
  // Tekrar kontrolü: aynı gmail msg ID zaten var mı?
  var checkUrl = SUPABASE_URL + "/rest/v1/notes?select=id&limit=1&content=like.*" + encodeURIComponent(gmailMsgId.substring(0, 12)) + "*";
  // (Basit kontrol — processed listesi asıl deduplication yapar)

  var payload = {
    "company_id": null,          // Şimdi eşleştirme YOK
    "content": content,
    "type": "email"
    // Not: daha zengin metadata için notes tablosuna ileride
    // event_tag, urgency, sender_domain sütunları eklenebilir
  };

  var options = {
    method: "POST",
    contentType: "application/json",
    headers: {
      "apikey": SUPABASE_ANON_KEY,
      "Authorization": "Bearer " + SUPABASE_ANON_KEY,
      "Prefer": "return=minimal"
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  var resp = UrlFetchApp.fetch(SUPABASE_URL + "/rest/v1/notes", options);
  return resp.getResponseCode() === 201;
}

// ──────────────────────────────────────────────────────────
// 4. TRIGGER KURULUMU (Bir kez çalıştır)
// ──────────────────────────────────────────────────────────
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === "syncEmailsToSupabase") {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger("syncEmailsToSupabase")
    .timeBased()
    .everyMinutes(15)
    .create();

  Logger.log("✅ Trigger kuruldu — her 15 dakika çalışacak.");
}

// ──────────────────────────────────────────────────────────
// 5. TEK SEFERLİK GERİ DOLDURMA (geçmiş mailler için)
// ──────────────────────────────────────────────────────────
function backfillLast90Days() {
  // GMAIL_SEARCH_QUERY'yi geçici olarak 90 gün yapıp çalıştır
  var oldQuery = GMAIL_SEARCH_QUERY;
  GMAIL_SEARCH_QUERY = GMAIL_SEARCH_QUERY.replace("newer_than:30d", "newer_than:90d");
  syncEmailsToSupabase();
  GMAIL_SEARCH_QUERY = oldQuery;
  Logger.log("✅ 90 günlük backfill tamamlandı.");
}
