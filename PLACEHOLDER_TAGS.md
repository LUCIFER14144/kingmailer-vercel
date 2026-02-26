# KINGMAILER Placeholder Tag System

This file documents the comprehensive placeholder tag system for use in email subjects, body text, HTML templates, and PDF conversions. All placeholders are fully compatible and functional in all contexts.

---

## Placeholder Tag System

**Instructions:**
All placeholders below can be used in email subject lines, body text, HTML templates, and PDF attachments. They are fully compatible and will be dynamically replaced with realistic, randomized, or recipient-specific data during email generation. Placeholders are enclosed in double curly braces, e.g., `{{recipient_name}}`. Spintax syntax `{Option1|Option2}` is also supported for random phrase selection.

---

### 1. Recipient Tags

| Placeholder         | Description / Example                          |
|---------------------|------------------------------------------------|
| `{{recipient}}`     | Recipient’s email address (`john@example.com`) |
| `{{recipient_name}}`| Name from CSV or fallback (`John Doe`)         |
| `{{recipient_first}}`| First name only (`John`)                      |
| `{{recipient_last}}` | Last name only (`Doe`)                        |
| `{{recipient_formal}}`| Formal name (`Mr. John Doe`)                 |
| `{{recipient_company}}`| Company from CSV or fallback (`ACME Corp`)  |

---

### 2. Date & Time Tags

| Placeholder         | Description / Example                          |
|---------------------|------------------------------------------------|
| `{{date}}`          | Current date (`February 26, 2026`)             |
| `{{time}}`          | Current time (`03:45 PM`)                      |
| `{{year}}`          | Current year (`2026`)                          |
| `{{month}}`         | Current month (`February`)                     |
| `{{day}}`           | Current day (`26`)                             |

---

### 3. Unique Identifier Tags

| Placeholder         | Description / Example                          |
|---------------------|------------------------------------------------|
| `{{unique_id}}`     | 13-digit unique ID (`1677421234567`)           |
| `{{tracking_id}}`   | Random tracking number (`TRK-82736492`)        |
| `{{random_6}}`      | 6-char random string (`A7b9Qz`)                |
| `{{random_8}}`      | 8-char random string (`XyZ12aBc`)              |
| `{{random_upper_10}}`| 10 uppercase letters (`QWERTYUIOP`)           |
| `{{random_lower_12}}`| 12 lowercase letters (`qwertyuiopasd`)        |
| `{{random_alphanum_16}}`| 16 alphanumeric (`A1B2C3D4E5F6G7H8`)        |
| `{{invoice_number}}`| Random invoice (`INV-2026-8273`)               |

---

### 4. Custom Tags

| Placeholder         | Description / Example                          |
|---------------------|------------------------------------------------|
| `{{random_name}}`   | Full random person name (`Emily Johnson`)      |
| `{{random_company}}`| Random US company (`Global Solutions Inc.`)    |
| `{{random_phone}}`  | US phone number (`+1 (555) 123-4567`)          |
| `{{random_email}}`  | Random email (`jane.smith@innovatech.com`)     |
| `{{random_url}}`    | Random URL (`https://www.techgroup.com`)       |
| `{{random_percent}}`| Random percent (`23%`)                         |
| `{{random_currency}}`| Random dollar amount (`$1,234.56`)            |

---

### 5. Address Tags

| Placeholder         | Description / Example                          |
|---------------------|------------------------------------------------|
| `{{address_street}}`| Street address (`123 Main St.`)                |
| `{{address_city}}`  | City (`San Francisco`)                         |
| `{{address_state}}` | State (`CA`)                                   |
| `{{address_zip}}`   | ZIP code (`94105`)                             |
| `{{address_full}}`  | Full address (`123 Main St., San Francisco, CA 94105`) |

---

### 6. Sender Tags

| Placeholder         | Description / Example                          |
|---------------------|------------------------------------------------|
| `{{sender_name}}`   | Sender’s name (`Michael Brown`)                |
| `{{sender_company}}`| Sender’s company (`Premier Services LLC`)      |
| `{{sent_from}}`     | “Sent from” tag (`Sent from New York, NY`)     |
| `{{sender_email}}`  | Sender’s email (`michael@premierservices.com`) |

---

### 7. Spintax & CSV Column Tags

- **Spintax:** `{Hello|Hi|Greetings}` → Randomly selects one option.
- **CSV Columns:** Any CSV column header can be used as a placeholder, e.g., `{{phone}}`, `{{department}}`.

---

**Implementation Notes:**
- All placeholders are replaced dynamically and work across all email contexts (subject, body, HTML, PDF).
- Random name generators use authentic US names for personalization.
- Address and company tags are generated with geographic realism.
- Spintax and CSV column tags allow for advanced customization and personalization.

---

**Example Usage:**

- Subject: `{Hi|Hello} {{recipient_first}}, Your Invoice {{invoice_number}} from {{random_company}}`
- Body: `Dear {{recipient_formal}},\nYour order {{unique_id}} will be shipped to {{address_full}}.\nContact us at {{sender_email}}.`
- HTML: `<h1>Welcome, {{recipient_name}}!</h1><p>Special offer from {{random_company}} valid until {{date}}.</p>`
- PDF: `Invoice Number: {{invoice_number}}\nAmount Due: {{random_currency}}\nDate: {{date}}`

---

**To Implement:**
Integrate these placeholders into your email automation system. Ensure all tags are supported in your template engine and that random generators produce realistic, professional data. Sender fields should use authentic names for maximum personalization.
