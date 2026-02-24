function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('IBS Exhibitors')
      .addItem('Import Exhibitors', 'importExhibitors')
      .addToUi();
}

function importExhibitors() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  // Optional: clear existing data
  // sheet.clear();
  
  // Set headers if not present or just append
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["Company", "Segment", "City", "State/Country", "Booth", "Website", "Description", "Role"]);
  }

  var baseUrl = "https://www.buildersshow.com/search-api/exhibitors";
  var segments = ["BB", "MP", "CT", "GP", "IF", "OL"];
  var startRow = 1;
  var pageSize = 100;
  var showID = 22;
  
  var allRows = [];
  
  // Create a cleanHtml helper
  var cleanHtml = function(raw) {
    if (!raw) return "";
    var stripped = raw.replace(/<[^>]*>?/gm, "");
    // Basic decode for common entities
    stripped = stripped.replace(/&amp;/g, "&")
                       .replace(/&lt;/g, "<")
                       .replace(/&gt;/g, ">")
                       .replace(/&quot;/g, "\"")
                       .replace(/&#39;/g, "'")
                       .replace(/&nbsp;/g, " ");
    return stripped.trim();
  };

  while (true) {
    // Construct Query String manually to handle multiple 'segments' parameters correctly
    var queryString = "startrow=" + startRow + "&pagesize=" + pageSize + "&showID=" + showID;
    for (var i = 0; i < segments.length; i++) {
        queryString += "&segments=" + segments[i];
    }
    
    var url = baseUrl + "?" + queryString;
    
    var options = {
      "method": "get",
      "headers": {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
      },
      "muteHttpExceptions": true
    };
    
    try {
      Logger.log("Fetching: " + url);
      var response = UrlFetchApp.fetch(url, options);
      var responseCode = response.getResponseCode();
      
      if (responseCode !== 200) {
        Logger.log("Failed with code: " + responseCode);
        SpreadsheetApp.getUi().alert("Error fetching data. Code: " + responseCode);
        break;
      }
      
      var json = JSON.parse(response.getContentText());
      var items = json.Results || [];
      
      if (items.length === 0) {
        Logger.log("No more items found.");
        break;
      }
      
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var booths = item.booths || [];
        var boothNumber = booths.length > 0 ? booths[0].booth : "";
        var productSegment = item.productSegment || "";
        
        var role = "Product";
        if (productSegment && productSegment.indexOf("Business Management") !== -1) {
          role = "Service";
        }
        
        var redirectName = item.redirectName || "";
        var websiteUrl = redirectName ? "https://www.buildersshow.com/exhibitor/" + redirectName : "";
        
        var description = cleanHtml(item.description);

        allRows.push([
          item.companyName,
          productSegment,
          item.city,
          item.stateCountry,
          boothNumber,
          websiteUrl,
          description,
          role
        ]);
      }
      
      Logger.log("Fetched " + items.length + " records. Total buffered: " + allRows.length);
      startRow += pageSize;
      
      // Sleep to avoid hitting rate limits
      Utilities.sleep(1000);
      
    } catch (e) {
      Logger.log("Error: " + e);
      SpreadsheetApp.getUi().alert("Exception: " + e);
      break;
    }
  }
  
  if (allRows.length > 0) {
    // Write in batches if necessary, but 2000 rows is fine for one call usually.
    // getRange(row, col, numRows, numCols)
    // Starting after the last row
    var startOutputRow = sheet.getLastRow() + 1;
    sheet.getRange(startOutputRow, 1, allRows.length, allRows[0].length).setValues(allRows);
    SpreadsheetApp.getUi().alert("Done! Imported " + allRows.length + " exhibitors.");
  } else {
    SpreadsheetApp.getUi().alert("No data found or imported.");
  }
}
