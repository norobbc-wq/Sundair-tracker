import json
import re
import datetime
from playwright.sync_api import sync_playwright

def scrape_sundair():
    today = datetime.date.today()
    six_months_later = today + datetime.timedelta(days=180)
    
    routes = [
        {"id": "BER_DAM", "from": "BER", "to": "DAM"},
        {"id": "DAM_BER", "from": "DAM", "to": "BER"}
    ]
    
    extracted_data = {"BER_DAM": [], "DAM_BER": []}

    try:
        with sync_playwright() as p:
            # تشغيل المتصفح بوضع الحماية لمنع الحظر والانهيار
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1400, "height": 900}
            )
            page = context.new_page()

            for route in routes:
                route_id = route["id"]
                try:
                    print(f"جاري معالجة المسار: {route_id}")
                    # تحميل الصفحة بشرط تخفيف الانتظار لتجنب الـ Timeout
                    page.goto("https://www.sundair.com/booking/#/", wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(3000)

                    # معالجة موافقة الكوكيز بأمان
                    try:
                        for selector in ["button:has-text('Akzeptieren')", "button:has-text('Accept')", ".cookie-btn"]:
                            btn = page.query_selector(selector)
                            if btn and btn.is_visible():
                                btn.click()
                                page.wait_for_timeout(1000)
                                break
                    except Exception:
                        pass

                    page.wait_for_timeout(3000)

                    # قراءة محتوى الصفحة
                    page_text = page.evaluate("() => document.body.innerText")
                    lines = page_text.split('\n')
                    
                    current_flight = {}
                    for line in lines:
                        line = line.strip()
                        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
                        if date_match:
                            d_str = date_match.group(1)
                            try:
                                d_obj = datetime.datetime.strptime(d_str, "%d.%m.%Y").date()
                                if today <= d_obj <= six_months_later:
                                    if current_flight and "date" in current_flight:
                                        extracted_data[route_id].append(current_flight)
                                    current_flight = {
                                        "date": d_str, 
                                        "price": "غير متوفر", 
                                        "status": "غير متاح"
                                    }
                            except ValueError:
                                pass

                        price_match = re.search(r'(\d+[\.,]\d{2}\s*€)', line)
                        if price_match and current_flight:
                            current_flight["price"] = price_match.group(1).replace(',', '.')
                            current_flight["status"] = "متاح"

                    if current_flight and "date" in current_flight:
                        extracted_data[route_id].append(current_flight)

                except Exception as route_err:
                    print(f"تنبيه: تعذر إكمال جلب المسار {route_id}: {route_err}")

            browser.close()
    except Exception as sys_err:
        print(f"خطأ في تشغيل المحاكي: {sys_err}")

    # التعديل الرئيسي: بناء الملف دائماً حتى لو فشل جلب بعض البيانات لمنع انهيار الـ Workflow
    build_interactive_html(extracted_data, today, six_months_later)

def build_interactive_html(data, start_date, end_date):
    json_data = json.dumps(data, ensure_ascii=False)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    period_str = f"من {start_date.strftime('%d.%m.%Y')} حتى {end_date.strftime('%d.%m.%Y')}"

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>رحلات Sundair المتاحة</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; padding: 15px; color: #1c1e21; }}
        .card {{ background: white; padding: 25px; border-radius: 16px; max-width: 680px; margin: auto; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
        h2 {{ text-align: center; color: #0056b3; margin-top: 0; }}
        .subtitle {{ text-align: center; font-size: 0.85em; color: #65676b; margin-bottom: 20px; }}
        .action-area {{ text-align: center; margin-bottom: 20px; }}
        .btn-trigger {{ background: #28a745; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; }}
        .filter-box {{ background: #f7f8fa; padding: 15px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #e4e6eb; }}
        select {{ width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #ccd0d5; font-size: 15px; background: white; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px 10px; border-bottom: 1px solid #e4e6eb; text-align: right; }}
        th {{ background: #f5f6f7; color: #4b4f56; }}
        .price-available {{ color: #2e7d32; font-weight: bold; }}
        .price-unavailable {{ color: #d32f2f; font-weight: bold; }}
        .badge {{ background: #0056b3; color: white; padding: 3px 8px; border-radius: 6px; font-size: 0.8em; }}
        .empty-msg {{ text-align: center; color: #8d949e; padding: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>✈️ جدول رحلات Sundair (6 أشهر)</h2>
        <div class="subtitle">
            الفترة المغطاة: <strong>{period_str}</strong><br>
            آخر تحديث آلي: {now_str}
        </div>

        <div class="action-area">
            <button id="triggerBtn" onclick="triggerGitHubWorkflow()" class="btn-trigger">🔄 تحديث الأسعار فوراً</button>
        </div>

        <div class="filter-box">
            <label for="routeSelect">اختر اتجاه الرحلة:</label>
            <select id="routeSelect" onchange="renderFlights()">
                <option value="BER_DAM">برلين (BER) ⬅ دمشق (DAM)</option>
                <option value="DAM_BER">دمشق (DAM) ⬅ برلين (BER)</option>
            </select>
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

        function getDayName(dateStr) {{
            const parts = dateStr.split('.');
            const d = new Date(parts[2], parts[1] - 1, parts[0]);
            const days = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
            return days[d.getDay()];
        }}

        function renderFlights() {{
            const route = document.getElementById('routeSelect').value;
            const tbody = document.getElementById('flightsTable');
            tbody.innerHTML = '';

            const flights = allData[route] || [];

            if (flights.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="3" class="empty-msg">لا توجد رحلات معروضة حالياً أو جاري إعادة المحاولة.</td></tr>';
                return;
            }}

            flights.forEach(item => {{
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
            }});
        }}

        async function triggerGitHubWorkflow() {{
            let token = localStorage.getItem('gh_pat');
            if (!token) {{
                token = prompt('يرجى إدخال GitHub Personal Access Token:');
                if (token) {{
                    token = token.trim();
                    localStorage.setItem('gh_pat', token);
                }} else return;
            }}

            const pathSegments = window.location.pathname.split('/').filter(Boolean);
            const repoOwner = window.location.hostname.split('.')[0];
            const repoName = pathSegments.length > 0 ? pathSegments[0] : '';

            const btn = document.getElementById('triggerBtn');
            btn.innerText = '⏳ جاري إرسال الطلب...';
            btn.disabled = true;

            try {{
                const response = await fetch(`https://api.github.com/repos/${{repoOwner}}/${{repoName}}/actions/workflows/update.yml/dispatches`, {{
                    method: 'POST',
                    headers: {{
                        'Authorization': `Bearer ${{token}}`,
                        'Accept': 'application/vnd.github.v3+json',
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ ref: 'main' }})
                }});

                if (response.ok) alert('✅ تم إرسال طلب التحديث بنجاح!');
                else {{
                    alert('❌ فشل إرسال الطلب. تحقق من الرمز والصلاحيات.');
                    localStorage.removeItem('gh_pat');
                }}
            }} catch (err) {{
                alert('❌ حدث خطأ في الاتصال.');
            }} finally {{
                btn.innerText = '🔄 تحديث الأسعار فوراً';
                btn.disabled = false;
            }}
        }}

        window.onload = renderFlights;
    </script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    scrape_sundair()
