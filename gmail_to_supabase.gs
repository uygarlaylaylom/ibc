// ============================================================
// IBC / KBIS / Fuar Mailleri → Supabase Sync Script (Zero-Touch Pipeline V2)
// Gmail Apps Script — uygar@mercan.net Workspace'inde çalışır
// Her 15 dakikada otomatik tetiklenir
// ============================================================

// ──────────────────────────────────────────────────────────
// 1. AYARLAR
// ──────────────────────────────────────────────────────────
var SUPABASE_URL      = "https://voiexsboyzgglnmtinhf.supabase.co";
var SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZvaWV4c2JveXpnZ2xubXRpbmhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4OTIxODQsImV4cCI6MjA4NzQ2ODE4NH0.Q5-EXFDNVKAW_sCBp0KQRrv7xzziQqFuZ2MXqwbusdM";

// OpenAI AI key — Script Properties'ten okunur (kod içinde görünmez, GitHub'a gitmez)
// Kurulum: saveOpenAIKey() fonksiyonunu bir kez çalıştırın
var OPENAI_API_KEY = PropertiesService.getScriptProperties().getProperty("OPENAI_API_KEY") || "";
var OPENAI_ENABLED = true;  // false yaparsanız OpenAI atlanır ve düz metin atılır

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
var PROCESSED_KEY = "ibc_processed_ids_v3";

// ──────────────────────────────────────────────────────────
// 2. ANA FONKSİYON
// ──────────────────────────────────────────────────────────
function syncEmailsToSupabase() {
  var props = PropertiesService.getScriptProperties();
  var processedRaw = props.getProperty(PROCESSED_KEY) || "[]";
  var processed = JSON.parse(processedRaw);

  // 1. Supabase'ten Şirketleri Çek (Eşleştirme için)
  var companies = fetchCompanies();
  var companyNames = companies.map(function(c) { return c.company_name; }).join(", ");

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

      // Manuel filtreler ve etiketler
      var eventTag = detectEvent(fullText);
      var urgency = scoreUrgency(subject, body);
      var senderDomain = extractDomain(sender);

      // 2. OpenAI ile Tam Otonom Analiz
      var aiResult = null;
      var companyId = null;

      if (OPENAI_ENABLED && OPENAI_API_KEY) {
        aiResult = callOpenAI(subject, body, companyNames);
        // Eşleşen Şirketi Bul (Fuzzy Search in JS)
        if (aiResult && aiResult.FİRMA && aiResult.FİRMA !== "Listede Yok") {
           var matchStr = aiResult.FİRMA.toLowerCase();
           for (var i = 0; i < companies.length; i++) {
             // Çok yönlü eşleştirme (Şirket adı aiResult içinde geçiyorsa veya tam tersi)
             var compName = companies[i].company_name.toLowerCase();
             if (compName === matchStr || 
                 compName.indexOf(matchStr) > -1 ||
                 matchStr.indexOf(compName) > -1) {
                companyId = companies[i].id;
                aiResult.FİRMA = companies[i].company_name; // Eşleşen Net ismi yaz
                break;
             }
           }
        }
      }

      // Email İçeriğini Formatla
      var content = buildContent(subject, sender, senderDomain, dateObj, eventTag, urgency, body, aiResult);

      // 3. Email'i Activities Tablosuna Kaydet (Zero-Touch DB Insert)
      var emailPayload = {
        "company_id": companyId, // Eşleşmediyse null kalır ve Eşleşmemiş sekmesine düşer
        "content": content,
        "type": "email"
      };

      var success = insertActivity(emailPayload);
      if (success) {
        newProcessed.push(msgId);
        insertCount++;
        Logger.log("✅ [" + eventTag + "] " + subject + (companyId ? " (Eşleşti: " + aiResult.FİRMA + ")" : ""));

        // 4. Görev (Task) İsteği Varsa Kanban Board İçin Task Oluştur
        if (companyId && aiResult && aiResult.AKSİYON && 
            aiResult.AKSİYON.toLowerCase().indexOf("yok") === -1 && 
            aiResult.AKSİYON.toLowerCase() !== "sil") {
            
            var priorityLevel = "Medium";
            if (aiResult.ÖNCELİK) {
                if (aiResult.ÖNCELİK.toLowerCase().indexOf("yüksek") > -1) priorityLevel = "High";
                else if (aiResult.ÖNCELİK.toLowerCase().indexOf("düşük") > -1) priorityLevel = "Low";
            }

            var taskPayload = {
               "company_id": companyId,
               "content": "📧 **[Otomatik Action: " + subject + "]**\n" + aiResult.AKSİYON + "\n\nÜrünler: " + (aiResult.ÜRÜNLER || "-"),
               "type": "task",
               "status": "To Do",
               "priority": priorityLevel,
               "due_date": new Date().toISOString()
            };
            insertActivity(taskPayload);
            Logger.log("   📌 Görev oluşturuldu ve Kanban'a yollandı: " + aiResult.AKSİYON);
        }
      }
    });
  });

  // İşlenen ID'leri güncelle (son 1000 tut)
  var allProcessed = processed.concat(newProcessed);
  if (allProcessed.length > 1000) allProcessed = allProcessed.slice(-1000);
  props.setProperty(PROCESSED_KEY, JSON.stringify(allProcessed));

  Logger.log("─── Tamamlandı: " + insertCount + " yeni email Pipeline'dan geçti ───");
}

// ──────────────────────────────────────────────────────────
// 3. YARDIMCI FONKSİYONLAR
// ──────────────────────────────────────────────────────────

/**
 * 1. Supabase'ten güncel firma listesini çeker.
 */
function fetchCompanies() {
  var options = {
    method: "GET",
    headers: {
      "apikey": SUPABASE_ANON_KEY,
      "Authorization": "Bearer " + SUPABASE_ANON_KEY
    },
    muteHttpExceptions: true
  };
  var resp = UrlFetchApp.fetch(SUPABASE_URL + "/rest/v1/companies?select=id,company_name", options);
  if (resp.getResponseCode() === 200) {
    return JSON.parse(resp.getContentText());
  }
  Logger.log("❌ Supabase firmaları çekilemedi: " + resp.getContentText());
  return [];
}

/**
 * 2. OpenAI (GPT-4o-mini) kullanarak Email üzerinden yapılandırılmış JSON çıkartır.
 */
function callOpenAI(subject, body, companyListStr) {
  try {
    var ibsTree = "1-Structural: Framing, Concrete\n2-Building Envelope: Siding, Waterproofing\n3-Roofing: Asphalt, Metal\n4-Windows & Doors\n5-Insulation\n6-HVAC\n7-Plumbing\n8-Electrical\n9-Smart Home\n10-Kitchen & Bath\n11-Interior Finishes\n12-Outdoor Living\n13-Site & Landscape\n14-Materials: Stone, Aluminum\n15-Software & Services";

    var systemPrompt = "Sen bir fuar asistanısın. E-postayı analiz edip kesinlikle geçerli bir JSON objesi döndürmelisin.";
    
    var userPrompt = "EMAİL KONUSU: " + subject + "\n\nEMAIL METNİ: " + body.substring(0, 1500) + "\n\n"
      + "IBS KATEGORİSİ AĞACI:\n" + ibsTree + "\n\n"
      + "FİRMA LİSTESİ (Sadece bu listeden seç, hiçbiri eşleşmiyorsa 'Listede Yok' yaz):\n" + companyListStr + "\n\n"
      + "Lütfen TÜRKÇE olarak aşağıdaki JSON formatında yanıtla (sadece geçerli JSON çıktısı ver):\n"
      + "{\n"
      + '  "FİRMA": "<Gönderenin firma adı listeden seç, yoksa Listede Yok>",\n'
      + '  "IBS_SEGMENT": "<en uygun kategori adı>",\n'
      + '  "ÜRÜNLER": "<Bahsedilen ürünler>",\n'
      + '  "AKSİYON": "<Somut eylem: Demo İste, Katalog İncele, Toplantı Ayarla, Yok, Sil>",\n'
      + '  "ÖNCELİK": "<Yüksek / Orta / Düşük>"\n'
      + "}";

    var payload = {
      "model": "gpt-4o-mini",
      "response_format": { "type": "json_object" },
      "messages": [
        { "role": "system", "content": systemPrompt },
        { "role": "user", "content": userPrompt }
      ],
      "temperature": 0.1
    };

    var options = {
      method: "POST",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + OPENAI_API_KEY },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var url = "https://api.openai.com/v1/chat/completions";
    var resp = UrlFetchApp.fetch(url, options);
    
    if (resp.getResponseCode() === 200) {
      var jsonStr = JSON.parse(resp.getContentText()).choices[0].message.content;
      return JSON.parse(jsonStr);
    } else {
      Logger.log("OpenAI Error: " + resp.getContentText());
      return null;
    }
  } catch(e) {
    Logger.log("OpenAI Exception: " + e);
    return null;
  }
}

function detectEvent(text) {
  var t = text.toLowerCase();
  if (t.indexOf("kbis") !== -1 || t.indexOf("kitchen bath") !== -1 || t.indexOf("kitchen & bath") !== -1) return "KBIS";
  if (t.indexOf("ibs") !== -1 || t.indexOf("international builders") !== -1 || t.indexOf("ibsvegas") !== -1) return "IBS";
  if (t.indexOf("nahb") !== -1) return "NAHB";
  if (t.indexOf("nkba") !== -1) return "NKBA";
  if (t.indexOf("orlando") !== -1) return "KBIS-Orlando";
  if (t.indexOf("las vegas") !== -1) return "IBS-LasVegas";
  if (t.indexOf("trade show") !== -1 || t.indexOf("exhibitor") !== -1) return "TradeShow";
  return "Fuar-Genel";
}

function scoreUrgency(subject, body) {
  var score = 0;
  var s = (subject + " " + body).toLowerCase();
  var highSignals = ["urgent", "deadline", "offer", "price list", "quote", "fiyat", "teklif", "meeting", "appointment", "invite", "exclusive", "limited", "today", "asap", "expires", "katalog", "catalog", "sample", "demo request"];
  var medSignals  = ["new product", "launch", "announcement", "visit", "schedule", "brochure", "partnership", "distributor", "follow up", "follow-up", "product line"];
  highSignals.forEach(function(w) { if (s.indexOf(w) !== -1) score += 2; });
  medSignals.forEach(function(w)  { if (s.indexOf(w) !== -1) score += 1; });
  return Math.min(score, 10);
}

function extractDomain(sender) {
  var match = sender.match(/@([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})/);
  return match ? match[1] : "bilinmiyor";
}

function buildContent(subject, sender, domain, dateObj, eventTag, urgency, body, aiResult) {
  var dateStr = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), "dd.MM.yyyy HH:mm");
  var urgencyBadge = urgency >= 7 ? "🔴 YÜKSEK" : urgency >= 4 ? "🟡 ORTA" : "🟢 Düşük";

  var base = "📧 **" + subject + "**\n\n"
       + "| Alan | Bilgi |\n"
       + "|------|-------|\n"
       + "| ✉️ Gönderen | " + sender + " |\n"
       + "| 🌐 Domain | " + domain + " |\n"
       + "| 🎪 Fuar | " + eventTag + " |\n"
       + "| 🔥 Öncelik | " + urgencyBadge + " (" + urgency + "/10) |\n"
       + "| 📅 Tarih | " + dateStr + " |\n\n"
       + "---\n"
       + body.substring(0, 1500) + "\n\n";

  if (aiResult) {
    base += "---\n🤖 **ChatGPT Analizi (Zero-Touch V2)**\n"
         + "- **Eşleşen Firma:** " + (aiResult.FİRMA || "Yok") + "\n"
         + "- **IBS Segmenti:** " + (aiResult.IBS_SEGMENT || "Yok") + "\n"
         + "- **Ürünler:** " + (aiResult.ÜRÜNLER || "-") + "\n"
         + "- **Aksiyon:** " + (aiResult.AKSİYON || "Yok") + "\n"
         + "- **Yapay Zeka Önceliği:** " + (aiResult.ÖNCELİK || "Normal");
  }
  return base;
}

function insertActivity(payload) {
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
  var resp = UrlFetchApp.fetch(SUPABASE_URL + "/rest/v1/activities", options);
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
  var oldQuery = GMAIL_SEARCH_QUERY;
  GMAIL_SEARCH_QUERY = GMAIL_SEARCH_QUERY.replace("newer_than:30d", "newer_than:90d");
  syncEmailsToSupabase();
  GMAIL_SEARCH_QUERY = oldQuery;
  Logger.log("✅ 90 günlük backfill tamamlandı.");
}

// ──────────────────────────────────────────────────────────
// 6. OPENAI KEY KAYIT — Sadece bir kez çalıştırın!
// ──────────────────────────────────────────────────────────
function saveOpenAIKey() {
  // OPENAI Key'inizi aşağıya tırnak içine yapıştırın
  var key = "sk-proj-...(BURAYA_YAPISTIRIN)..."; 
  PropertiesService.getScriptProperties().setProperty("OPENAI_API_KEY", key);
  Logger.log("✅ OpenAI API key Script Properties'e kaydedildi. Güvenlik için bu satırı silebilirsiniz.");
}
