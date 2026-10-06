from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)


OUT = Path(__file__).resolve().parents[1] / "output" / "pdf" / "BNP1_Specification.pdf"


def p(text, style):
    return Paragraph(text, style)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#78BFA8"))
    canvas.line(doc.leftMargin, 0.55 * inch, letter[0] - doc.rightMargin, 0.55 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#4A5568"))
    canvas.drawString(doc.leftMargin, 0.36 * inch, "BNP/1 Binary Network Protocol - Network Architecture Project")
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.36 * inch, f"Page {doc.page}")
    canvas.restoreState()


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=0.58 * inch,
                            rightMargin=0.58 * inch, topMargin=0.52 * inch,
                            bottomMargin=0.72 * inch, title="BNP/1 Specification")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold",
                           fontSize=22, leading=25, textColor=colors.HexColor("#123B35"),
                           alignment=TA_CENTER, spaceAfter=5)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=9.5, leading=12,
                              textColor=colors.HexColor("#4A5568"), alignment=TA_CENTER, spaceAfter=12)
    h = ParagraphStyle("Heading", parent=styles["Heading2"], fontName="Helvetica-Bold",
                       fontSize=12, leading=14, textColor=colors.HexColor("#0A6C5B"),
                       spaceBefore=7, spaceAfter=3)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                          fontSize=8.35, leading=10.4, spaceAfter=5)
    small = ParagraphStyle("Small", parent=body, fontSize=7.7, leading=9.1, spaceAfter=0)
    cell = ParagraphStyle("Cell", parent=body, fontSize=7.2, leading=8.3, spaceAfter=0)
    emphasis = ParagraphStyle("Emphasis", parent=body, fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#A85100"), spaceBefore=3, spaceAfter=4)

    story = [p("BNP/1", title), p("Binary Network Protocol, version 1 - static file fetch over TCP", subtitle)]
    story += [p("1. Purpose and connection model", h),
              p("BNP/1 carries one static-file GET request and its response in binary frames. Start a server with <b>bserve ROOT PORT</b>; fetch with <b>bcurl [-v] HOST:PORT/PATH</b>. A client creates exactly one TCP connection for its requested URL and never opens a second connection. A connection may carry further ordered request/reply exchanges until a peer closes it or a framing-level error prevents safe resynchronisation.", body),
              p("All multibyte integers are unsigned big-endian. Text is UTF-8 unless stated otherwise. The implementation accepts payloads through 8,388,608 bytes and carries arbitrary body bytes without text conversion.", body),
              p("2. Frame layer", h)]

    frame_data = [[p("Offset", cell), p("Width", cell), p("Field", cell), p("Meaning", cell)],
                  [p("0", cell), p("2", cell), p("magic", cell), p("ASCII BN (42 4e)", cell)],
                  [p("2", cell), p("1", cell), p("version", cell), p("1 for this specification", cell)],
                  [p("3", cell), p("1", cell), p("type", cell), p("1 request; 2 response; other values are extensions", cell)],
                  [p("4", cell), p("1", cell), p("flags", cell), p("zero in v1; receiver ignores it", cell)],
                  [p("5", cell), p("1", cell), p("reserved", cell), p("MUST be zero", cell)],
                  [p("6", cell), p("2", cell), p("stream ID", cell), p("client-chosen nonzero correlation value", cell)],
                  [p("8", cell), p("4", cell), p("payload length", cell), p("number of following payload bytes", cell)]]
    table = Table(frame_data, colWidths=[0.45*inch, 0.45*inch, 1.08*inch, 4.55*inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D9F1E9")),
                               ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#123B35")),
                               ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                               ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#9DB9B0")),
                               ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                               ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
                               ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    story += [table, Spacer(1, 4),
              p("The fixed header establishes exactly where a frame ends. Magic rejects accidental traffic; version and type permit evolution. The 16-bit stream ID supports correlation, and a 32-bit declared length supports binary files while the 8 MiB cap limits allocation. Flags and one reserved byte leave defined space for v2.", body),
              p("Extension rule: a receiver meeting a frame type it does not know MUST read and discard exactly its declared payload length, then continue with the next frame. It must not inspect unknown fields or close a sound connection merely because the type is unfamiliar.", emphasis),
              p("If magic, version, reserved byte, length limit, or a complete payload cannot be read, framing is malformed and the connection closes because boundaries cannot be trusted. A known request frame with a bad payload receives 400 on its stream and the connection stays usable.", body),
              p("3. Header representation", h),
              p("After a request path or response status, headers are <b>count:u8</b>, then count entries. Each starts with <b>name_id:u8</b>. IDs 1-10 name: 1 host, 2 content-type, 3 content-length, 4 connection, 5 date, 6 server, 7 accept, 8 user-agent, 9 cache-control, 10 last-modified. An indexed entry continues <b>value_length:u16, value:utf8</b>.", body),
              p("For another name, send <b>name_id=0, name_length:u8, name:ASCII, value_length:u16, value:UTF-8</b>. Literal names are nonempty. Indexing stable common names saves bytes; length-prefixed literals allow extensions without a registry. Unknown nonzero name IDs are malformed in v1 because their names are not self-delimiting.", body),
              PageBreak(),
              p("BNP/1 - Specification (continued)", ParagraphStyle("Continued", parent=title, fontSize=16, leading=18, spaceAfter=8)),
              p("4. Request and response payloads", h),
              p("A request (type 1) is <b>method:u8, path_length:u16, path:UTF-8, headers</b>. Method 1 is GET and is the only valid method. A path starts with /, has no query or fragment, and has no empty, . or .. component. The server resolves it beneath its configured root; a missing regular file is 404.", body),
              p("A response (type 2) is <b>status:u16, headers, body_length:u32, body</b>. body_length consumes the remaining payload exactly. The server sends content-type, content-length and connection: keep-alive. It returns 200 for a found file, 404 when absent, 400 for a well-framed bad request, and 500 for an internal file error. bcurl writes body bytes only to stdout; -v writes decoded metadata and frame hexdumps to stderr. It exits 0 for a status below 400, 4 for 4xx, and 5 for 5xx.", body),
              p("5. Receiver requirements", h),
              p("Read TCP until every declared byte arrives; recv calls are not frame boundaries. Before allocation, check every length against the remaining payload and implementation cap. Reject invalid UTF-8, invalid header IDs, empty literal header names, trailing bytes in a known payload, invalid status, and root-escaping paths. These checks prevent desynchronisation and unsafe file access.", body),
              p("Known malformed request payloads produce a type-2 response with status 400. Unknown frame types are skipped only after all their declared bytes have been consumed. This is the compatibility mechanism that lets a later protocol version add frame types without breaking an older peer.", body),
              p("6. Interoperability example", h),
              p("For <b>localhost:9000/index.html</b>, bcurl sends a type-1 stream-1 frame whose request payload is GET (01), path /index.html, indexed host localhost:9000, and indexed user-agent bcurl/1. bserve answers on stream 1 with status 200, indexed content-type text/html, indexed content-length, indexed connection keep-alive, then the exact file bytes. The submitted annotated hexdump records every byte of this exchange.", body),
              p("Implementation checklist", h)]
    checks = [[p("Client", cell), p("Build one binary request frame, read one response, send body to stdout, hexdump frames with -v, use no second connection, return nonzero for 4xx/5xx.", cell)],
              [p("Server", cell), p("Accept TCP, read complete binary frames despite segmentation, safely map paths under root, return status/headers/body, 404 missing files, 400 malformed known requests, and preserve usable connections.", cell)],
              [p("Protocol", cell), p("Fixed 12-byte header, numbered first ten header names, length-prefixed remaining names, checked lengths, and mandatory unknown-frame skip rule.", cell)]]
    checklist = Table(checks, colWidths=[0.75*inch, 5.78*inch])
    checklist.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), colors.HexColor("#D9F1E9")),
                                   ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                                   ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#9DB9B0")),
                                   ("VALIGN", (0,0), (-1,-1), "TOP"),
                                   ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
                                   ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    story.append(checklist)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
