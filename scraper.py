import json
import re
import datetime
from playwright.sync_api import sync_playwright

def scrape_sundair():
    routes = [
        {"id": "BER_DAM", "from": "BER", "to": "DAM"},
        {"id": "DAM_BER", "from": "DAM", "to": "BER"}
    ]
    
    extracted_data = {"BER_DAM": [], "DAM_BER": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for route in routes:
            route_id = route["id"]
            try:
                page.goto("https://www.sundair.com/booking/#/", wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(4000)

                # إغلاق تنبيه الكوكيز إن وجد
                try:
                    cookie_btn = page.query_selector("button:has-text('Akzeptieren'), button:has-text('Accept')")
                    if cookie_btn:
                        cookie_btn.click()
                        page.wait_for_timeout(1000)
                except Exception:
                    pass

                # استخراج النصوص
                page_text = page.evaluate("() => document.body.innerText")
                lines = page_text.split('\n')
                
                current_flight = {}
                for line in lines:
                    line = line.strip()
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
                    if date_match:
                        if current_flight and "date" in current_flight:
                            extracted_data[route_id].append(current_flight)
                        current_flight = {"date": date_match.group(1), "price": "غير متوفر", "status": "NICHT VERFÜGBAR"}
                    
                    price_match = re.search(r'(\d+[\.,]\d{2}\s*€)', line)
                    if price_match and current_flight:
                        current_flight["price"] = price_match.group(1).replace(',', '.')
                        current_flight["status"] = "متاح"

                if current_flight and "date" in current_flight:
                    extracted_data[route_id].append(current_flight)

            except Exception as e:
                print(f"خطأ أثناء جلب {route_id}: {e}")

        browser.close()

    build_interactive_html(extracted_data)

def build_interactive_html(data):
    json_data = json.dumps(data, ensure_ascii=False)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>أسعار Sundair الحية</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f9; padding: 15px; color: #333; }}
        .card {{ background: white; padding: 20px; border-radius: 14px; max-width: 650px; margin: auto; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }}
        h2 {{ text-align: center; color: #0056b3; margin-top: 0; }}
        .filter-box {{ background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #e9ecef; }}
        .form-group {{ margin-bottom: 10px; display: flex; flex-direction: column; gap: 5px; }}
        label {{ font-weight: bold; font-size: 0.9em; }}
        select, input {{ padding: 10px; border-radius: 8px; border: 1px solid #ccc; font-size: 14px; background: white; }}
        .row {{ display: flex; gap: 10px; }}
        .row .form-group {{ flex: 1; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px 10px; border-bottom: 1px solid #eee; text-align: right; font-size: 0.95em; }}
        th {{ background: #e9ecef; color: #495057; }}
        .price-available {{ color: #28a745; font-weight: bold; }}
        .price-unavailable {{ color: #dc3545; font-weight: bold; }}
        .badge {{ background: #0056b3; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; }}
        .updated {{ font-size: 0.8em; color: #666; text-align: center; margin-bottom: 15px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>📊 أسعار Sundair الحية</h2>
        <div class="updated">آخر تحديث حقيقي: {now}</div>

        <div class="filter-box">
            <div class="form-group">
                <label>اتجاه الرحلة (تغيير الوجهة):</label>
                <select id="routeSelect" onchange="filterFlights()">
                    <option value="BER_DAM">برلين (BER) ⬅ دمشق (DAM)</option>
                    <option value="DAM_BER">دمشق (DAM) ⬅ برلين (BER)</option>
                </select>
            </div>
            
            <div class="row">
                <div class="form-group">
                    <label>من تاريخ:</label>
                    <input type="date" id="startDate" value="2026-09-06" onchange="filterFlights()">
                </div>
                <div class="form-group">
                    <label>إلى تاريخ:</label>
                    <input type="date" id="endDate" value="2026-12-31" onchange="filterFlights()">
                </div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>اليوم والتاريخ</th>
                    <th>السعر الحقيقي</th>
                    <th>الحالة</th>
                </tr>
            </thead>
            <tbody id="flightsTable"></tbody>
        </table>
    </div>

    <script>
        const allData = {json_data};

        function parseGermanDateStr(dateStr) {{
            const parts = dateStr.split('.');
            return `${{parts[2]}}-${{parts[1]}}-${{parts[0]}}`;
        }}

        function getDayName(dateStr) {{
            const parts = dateStr.split('.');
            const d = new Date(parts[2], parts[1] - 1, parts[0]);
            const days = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
            return days[d.getDay()];
        }}

        function getDayNum(dateStr) {{
            const parts = dateStr.split('.');
            const d = new Date(parts[2], parts[1] - 1, parts[0]);
            return d.getDay();
        }}

        function filterFlights() {{
            const route = document.getElementById('routeSelect').value;
            const startVal = document.getElementById('startDate').value;
            const endVal = document.getElementById('endDate').value;

            const tbody = document.getElementById('flightsTable');
            tbody.innerHTML = '';

            const flights = allData[route] || [];

            flights.forEach(item => {{
                const isoDate = parseGermanDateStr(item.date);
                const dayNum = getDayNum(item.date);
                const isTueOrSat = (dayNum === 2 || dayNum === 6);

                let inRange = true;
                if (startVal && isoDate < startVal) inRange = false;
                if (endVal && isoDate > endVal) inRange = false;

                if (isTueOrSat && inRange) {{
                    const isAvail = item.price !== 'غير متوفر';
                    const priceClass = isAvail ? 'price-available' : 'price-unavailable';
                    const dayName = getDayName(item.date);

                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><span class="badge">${{dayName}}</span> ${{item.date}}</td>
                        <td class="${{priceClass}}">${{item.price}}</td>
                        <td>${{item.status}}</td>
                    `;
                    tbody.appendChild(tr);
                }}
            }});

            if (tbody.children.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:#888;">لا توجد رحلات مطابقة للفلاتر المحددة</td></tr>';
            }}
        }}

        window.onload = filterFlights;
    </script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    scrape_sundair()
