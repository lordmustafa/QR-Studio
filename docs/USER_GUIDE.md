---
title: User guide
description: How to make QR codes with QR Studio, the free QR code generator for Windows and macOS. Links, Wi-Fi, contacts, WhatsApp, colors, logos and export.
---

# QR Studio user guide

QR Studio has four pages in the sidebar:

| Page | Use it to |
|---|---|
| **New code** | make one QR code and design it |
| **Many codes** | make a folder of codes from a list or a file |
| **Read a code** | read a QR code from an image or a screenshot |
| **History** | find and reopen codes you saved before |

The interface is in Arabic or English. It follows your system language at first. To change it, use
**Language** at the bottom of the sidebar. **Appearance** switches between light and dark.
When the window is narrow, the sidebar shrinks to icons. On the New code page, the editor and the
preview become two tabs, **Edit** and **Preview**.

## Make a QR code

The **New code** page has three steps.

### 1. What is the code for?

Pick one of the ten types. Each type asks only for what it needs.

| Type | Fields | Tips |
|---|---|---|
| **Link** | Link | `example.com` is enough. `https://` is added for you. |
| **Text** | Text | Any text. Long text makes a denser code. |
| **Wi-Fi** | Network name, password, security, hidden network | WPA passwords have 8–63 characters. Choose `nopass` for an open network. |
| **Contact** | Name, company, job title, phone, email, website, address, note | Saved as a vCard that phones add to Contacts. Enter a name or a company. |
| **Email** | Email address, subject, message | Opens a new email with these filled in. |
| **SMS** | Phone number, message | Opens a new text message. |
| **Call** | Phone number | Dials the number. |
| **WhatsApp** | Phone number with country code, message | Write the number like `+9647701234567`. A number that starts with `0` and has no country code will not work. |
| **Location** | Latitude, longitude | Turn on **Use a Google Maps link** if some scanners do not open plain coordinates. |
| **Event** | Title, starts, ends, location, description | Dates look like `2026-12-31 18:30`. The time is optional. |

Fields marked `*` are required. Phone, number and date fields only accept characters that fit
them. Western digits and Arabic-Indic digits (٠١٢٣) both work.

If a field is wrong, it turns red when you leave it and shows what to fix. The preview waits until
the fields are valid.

### 2. Enter the details

The preview updates as you type, delete or paste. Under the preview, the app reads the code
back and shows:

- **✓ Ready to use**: the app scanned the code and got the same content.
- **⚠ Low contrast**: the code color is too close to the background, so some phones may not read it.
- **⚠ Light code on a dark background**: some scanners cannot read inverted codes.

### 3. Choose a look

- **Quick styles:** Classic, Ocean, Sunset, Forest, Royal and Ink. One click changes colors and shapes together.
- **Code color** and **Background**
- **Add a logo:** choose a PNG or JPG. Transparent PNGs look best.

**More options** opens the rest:

| Option | What it does |
|---|---|
| Fill | Solid color, or a gradient: horizontal, vertical, diagonal or radial |
| Second color | The end color of the gradient |
| Transparent background | PNG and SVG keep the transparency |
| Dots | Square, rounded, circle, gapped, diamond, vertical bars, horizontal bars |
| Corner frame / Corner center | Square, rounded, circle or leaf |
| Custom corner colors | Give the corners their own colors |
| Logo size, Plate behind logo | 5–30 % of the code. The plate keeps the logo readable. |
| Caption, Caption color | Text under the code, for example "Scan me". Arabic works. |
| Draw a frame, Frame color | A colored frame around the code and the caption |
| Error correction | L 7 %, M 15 %, Q 25 %, H 30 % of the code can be damaged and still scan. A logo sets it to H. |
| Quiet zone | The empty margin around the code, 0–10 modules. Keep at least 2. |
| Export size | 256, 512, 1024, 2048 or 4096 px |
| Reset design | Back to the default look |

### Save or share

- **Download** saves the file. Choose the type next to it: PNG, JPG, SVG, PDF, WEBP or BMP.
  `Ctrl+S` (Windows) or `Cmd+S` (macOS) does the same.
- **Copy image** puts the picture on the clipboard, so you can paste it into a chat or a document.
- **Copy content** copies the text inside the code, for example the full Wi-Fi string.

Saved and copied codes appear in **History**.

## Make many codes at once

1. Open **Many codes**.
2. Write one link or text per line, or click **Import file…** and choose a `.txt` or `.csv` file.
   In a CSV file, the column `data` holds the content and the column `filename` the file name.
   Without a `data` column, the first column is used. Without a `filename` column, files are
   named by number and content, for example `001_example_com_menu.png`.
3. Choose **Each line is** Text or Link, the file type and the folder.
4. Click **Create codes**. You can stop at any time. When it finishes, **Open folder** shows the files.

Every code uses the look you chose on the New code page.

Example CSV:

```csv
data,filename
https://example.com/menu,menu
https://example.com/wifi,wifi-guide
https://example.com/contact,contact
```

## Read a QR code

Open **Read a code**, then click **Open image…** or **Paste from clipboard**. A screenshot works.
For each code found you can copy the content, open the link, or click **Edit in Create** to change
it and make a new code.

## History

Codes you save or copy are listed with a thumbnail. Search by content, click **Open** to load the
code and its design back into New code, or **Delete** to remove it. **Clear all** asks first.

Wi-Fi passwords are not stored in history or settings.

## Tips for codes that always scan

- Dark code on a light background works with every scanner.
- Keep contrast high. The app warns you when it is too low.
- Leave a quiet zone of at least 2 modules.
- With a logo, keep it at 25 % or less and keep the plate on.
- For print, export **SVG** or **PDF**. They stay sharp at any size.
- A printed code should be at least 2 × 2 cm. Make it bigger if people scan it from far away.
- Short content makes a simpler code that scans faster. Use a short link when you can.

## Where QR Studio keeps its files

Settings, the last design and history are in a folder named `.qr_studio` in your home folder:

- Windows: `C:\Users\<you>\.qr_studio`
- macOS and Linux: `~/.qr_studio`

Delete that folder to reset the app.

## Problems

**Windows says "Windows protected your PC".**
The app is not signed with a paid certificate. Click **More info**, then **Run anyway**.

**macOS says the app "cannot be opened".**
Right-click the app, choose **Open**, then **Open** again. You only do this once.

**The ✓ does not appear.**
Raise the contrast, make the logo smaller, or raise error correction. Codes with round corners are
checked as if their corners were square, because the checker cannot read round corners. Real
phone cameras read them fine.

**"Too much data for one QR code."**
Shorten the content, or lower the error correction.
