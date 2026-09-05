import json
import re
import datetime
from playwright.sync_api import sync_playwright

def scrape_sundair():
    today = datetime.date.today()
    six_months_later = today + datetime.timedelta(days=180)
    
    routes = [
        {"id": "BER_DAM", "title": "برلين (BER) ⬅ دمشق (DAM)"},
        {"id": "DAM_BER", "title": "دمشق (DAM) ⬅ برلين (BER)"}
    ]
    
    extracted_data = {"BER_DAM": [], "DAM_BER": []}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # فتح صفحة الحجز
            page.goto("https://www.sundair.com/booking/#/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            # استخراج النص الكامل للصفحة
            page_text = page.evaluate("() => document.body.innerText")
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            
            # قراءة التواريخ والأسعار مباشرة
            parsed_flights = []
            current_item = {}
            
            for line in lines:
                # البحث عن التواريخ بفرمتة DD.MM.YYYY
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
                if date_match:
                    d_str = date_match.group(1)
                    try:
                        d_obj = datetime.datetime.strptime(d_str, "%d.%m.%Y").date()
                        if today <= d_obj <= six_months_later:
                            if current_item and "date" in current_item:
                                parsed_flights.append(current_item)
                            current_item = {"date": d_str, "price": "غير متوفر", "status": "متاح"}
                    except ValueError:
                        pass

                # البحث عن الأسعار باليورو
                price_match = re.search(r'(\d+[\.,]\d{2}\s*€|\d+\s*€)', line)
                if price_match and current_item:
                    current_item["price"] = price_match.group(1).replace(',', '.')

            if current_item and "date" in current_item:
                parsed_flights.append(current_item)

            # توزيع الرحلات المكتشفة على المسارات
            extracted_data["BER_DAM"] = parsed_flights
            extracted_data["DAM_BER"] = parsed_flights

            browser.close()
    except Exception as e:
        print(f"حدث خطأ أثناء الجمع: {e}")

    build_simple_html(extracted_data, today, six_months_later)

def build_simple_html(data, start_date, end_date):
    json_data = json.dumps(data, ensure_ascii=False)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    period_str = f"من {start_date.strftime('%d.%m.%Y')} حتى {end_date.strftime('%d.%m.%Y')}"

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>رحلات Sundair</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #f4f6f8; padding: 20px; direction: rtl; }}
        .container {{ max-width: 700px; margin: auto; background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        h2 {{ text-align: center; color: #004481; margin-bottom: 5px; }}
        .info {{ text-align: center; font-size: 0.85em; color: #666; margin-bottom: 20px; }}
        .select-box {{ margin-bottom: 20px; }}
        select {{ width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ccc; font-size: 1em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px; text-align: right; border-bottom: 1px solid #eee; }}
        th {{ background: #004481; color: white; }}
        .price {{ color: #2e7d32; font-weight: bold; font-size: 1.1em; }}
        .no-data {{ text-align: center; padding: 20px; color: #888; }}
        .day-badge {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; margin-left: 5px; color: #333; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>✈️ جدول رحلات Sundair</h2>
        <div class="info">
            الفترة: <strong>{period_str}</strong> | آخر تحديث تلقائي: {now_str}
        </div>

        <div class="select-box">
            <label>اختر خط الطيران:</label>
            <select id="routeSelect" onchange="showFlights()">
                <option value="BER_DAM">برلين (BER) ⬅ دمشق (DAM)</option>
                <option value="DAM_BER">دمشق (DAM) ⬅ برلين (BER)</option>
            </select>
        </div>

        <table>
            <thead>
                <tr>
                    <th>التاريخ واليوم</th>
                    <th>السعر</th>
                    <th>الحالة</th>
                </tr>
            </thead>
            <tbody id="flightsBody"></tbody>
        </table>
    </div>

    <script>
        const flightsData = {json_data};

        function getDayName(dateStr) {{
            const p = dateStr.split('.');
            const d = new Date(p[2], p[1] - 1, p[0]);
            return ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'][d.getDay()];
        }}

        function showFlights() {{
            const route = document.getElementById('routeSelect').value;
            const tbody = document.getElementById('flightsBody');
            tbody.innerHTML = '';

            const list = flightsData[route] || [];

            if (list.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="3" class="no-data">لا توجد رحلات مسجلة حالياً.</td></tr>';
                return;
            }}

            list.forEach(item => {{
                const day = getDayName(item.date);
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><span class="day-badge">${{day}}</span> ${{item.date}}</td>
                    <td class="price">${{item.price}}</td>
                    <td>${{item.status}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        window.onload = showFlights;
    </script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    scrape_sundair()
