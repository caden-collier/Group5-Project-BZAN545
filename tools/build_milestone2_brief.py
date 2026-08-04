from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "Milestone_02_Beginner_Group_Guide.docx"

BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
NAVY = "17365D"
LIGHT_BLUE = "E8EEF5"
LIGHT_GRAY = "F2F4F7"
MID_GRAY = "666666"
GREEN = "2E7D32"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths_dxa):
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    tbl_w.set(qn("w:w"), str(sum(widths_dxa)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = Inches(widths_dxa[idx] / 1440)
            tc_w = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
            tc_w.set(qn("w:w"), str(widths_dxa[idx]))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Page ")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._r.addnext(fld)


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    p.add_run(text)
    return p


def add_number(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    p.add_run(text)
    return p


def add_code_block(doc, lines):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [9360])
    cell = table.cell(0, 0)
    set_cell_shading(cell, LIGHT_GRAY)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    for index, line in enumerate(lines):
        run = p.add_run(line)
        run.font.name = "Consolas"
        run._element.rPr.rFonts.set(qn("w:ascii"), "Consolas")
        run._element.rPr.rFonts.set(qn("w:hAnsi"), "Consolas")
        run.font.size = Pt(9)
        if index < len(lines) - 1:
            run.add_break()
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def configure_styles(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for style_name, size, color, before, after in (
        ("Heading 1", 16, BLUE, 18, 10),
        ("Heading 2", 13, BLUE, 14, 7),
        ("Heading 3", 12, DARK_BLUE, 10, 5),
    ):
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    for style_name in ("List Bullet", "List Bullet 2", "List Number"):
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(11)


def add_header_footer(doc):
    section = doc.sections[0]
    header = section.header
    p = header.paragraphs[0]
    p.text = "BZAN 545 | Group 5 | Milestone 02"
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after = Pt(0)
    run = p.runs[0]
    run.font.name = "Calibri"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor.from_string(MID_GRAY)
    footer = section.footer
    add_page_number(footer.paragraphs[0])
    footer.paragraphs[0].runs[0].font.size = Pt(8.5)
    footer.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string(MID_GRAY)


def add_summary_table(doc):
    table = doc.add_table(rows=5, cols=2)
    table.style = "Table Grid"
    values = [
        ("Order date", "July 12, 2026"),
        ("Dataset size", "104 rows x 9 columns"),
        ("Raw-file status", "Preserved unchanged; SHA-256 verified"),
        ("Canvas deadline", "Wednesday, July 15, 2026 at 11:59 PM"),
        ("Submission status", "Not submitted; group review still required"),
    ]
    for row, (label, value) in zip(table.rows, values):
        row.cells[0].text = label
        row.cells[1].text = value
        set_cell_shading(row.cells[0], LIGHT_BLUE)
        row.cells[0].paragraphs[0].runs[0].bold = True
    set_table_geometry(table, [2700, 6660])


def build_document():
    doc = Document()
    configure_styles(doc)
    add_header_footer(doc)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("MILESTONE 02 BEGINNER GUIDE")
    run.font.name = "Calibri"
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(BLUE)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(5)
    run = title.add_run("First Orders Captured")
    run.font.name = "Calibri"
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)

    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(16)
    run = subtitle.add_run("A plain-language guide for sharing, checking, and submitting the work")
    run.font.size = Pt(12.5)
    run.font.color.rgb = RGBColor.from_string(MID_GRAY)

    lead = doc.add_table(rows=1, cols=1)
    set_table_geometry(lead, [9360])
    set_cell_shading(lead.cell(0, 0), "EAF4EA")
    p = lead.cell(0, 0).paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("Outcome: ")
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(GREEN)
    p.add_run("The July 12 orders source has been preserved unchanged and can be read successfully. Right now, these new files exist only on Caden's computer; they will become visible to the group after they are committed and pushed to GitHub.")

    doc.add_heading("Milestone requirement", level=1)
    p = doc.add_paragraph(
        "Canvas describes this as a quick progress check confirming that the team has begun preserving the transient daily orders source. The group must save an untouched raw copy and demonstrate that code can read it successfully."
    )
    p.paragraph_format.keep_with_next = True
    add_summary_table(doc)

    doc.add_heading("The big picture: your computer versus GitHub", level=1)
    doc.add_paragraph(
        "Think of the project as having two copies. Each teammate has a local copy stored on their own computer. GitHub holds the shared online copy. Changes made on one computer do not automatically appear for everyone else."
    )
    add_bullet(doc, "Local copy: the project folder on one person's computer.")
    add_bullet(doc, "GitHub copy: the shared version that the group can view online.")
    add_bullet(doc, "Push: send saved Git changes from one computer to GitHub.")
    add_bullet(doc, "Pull: download the newest GitHub changes to another computer.")
    add_bullet(doc, "Pull request: a GitHub review page where the group can inspect changes before adding them to the main project.")

    note = doc.add_table(rows=1, cols=1)
    set_table_geometry(note, [9360])
    set_cell_shading(note.cell(0, 0), "FFF4E5")
    p = note.cell(0, 0).paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("Important: ")
    r.bold = True
    p.add_run("The different folder location on each teammate's computer is not a problem. The project uses paths that start inside the repository, such as src/inspect_orders.py, rather than Caden's full Windows path.")

    doc.add_heading("What was completed", level=1)
    add_number(doc, "Downloaded the current daily orders CSV from the course-provided source.")
    add_number(doc, "Confirmed that the file represents orders dated July 12, 2026.")
    add_number(doc, "Stored an untouched copy in a date-partitioned raw-data directory.")
    add_number(doc, "Verified that the stored file is byte-for-byte identical to the download using SHA-256 hashes.")
    add_number(doc, "Created and ran a Python inspection script that reports the dataset structure and previews three records.")
    add_number(doc, "Prepared a Markdown evidence note containing the facts required for Canvas.")

    doc.add_page_break()
    doc.add_heading("Repository additions", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Path"
    table.rows[0].cells[1].text = "Purpose"
    for cell in table.rows[0].cells:
        set_cell_shading(cell, BLUE)
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.bold = True
    files = [
        ("data/bronze/orders/2026-07-12/orders.csv", "Untouched bronze source file for the July 12 capture."),
        ("src/inspect_orders.py", "Reads the CSV and prints rows, columns, dates, headers, and three sample records."),
        ("docs/milestones/milestone_02.md", "Records the verified facts, storage convention, and reproduction instructions."),
    ]
    for path, purpose in files:
        cells = table.add_row().cells
        cells[0].text = path
        cells[1].text = purpose
        cells[0].paragraphs[0].runs[0].font.name = "Consolas"
        cells[0].paragraphs[0].runs[0].font.size = Pt(9)
    set_table_geometry(table, [4100, 5260])

    doc.add_heading("What the Python file does", level=1)
    p = doc.add_paragraph(
        "The inspection script is evidence that the team can programmatically read the source. It is intentionally read-only and uses Python's built-in CSV support, so no additional packages are required."
    )
    for item in (
        "Opens the preserved CSV without changing it.",
        "Counts records and columns.",
        "Lists the column names.",
        "Extracts the represented order date.",
        "Prints the first three records for a quick visual check.",
    ):
        add_bullet(doc, item)

    doc.add_heading("How to run the Python check", level=1)
    doc.add_paragraph(
        "First, open the project folder in File Explorer. Right-click an empty area inside the folder and choose Open Git Bash here. This starts Git Bash in the correct location, so you do not need to type anyone's personal folder path."
    )
    p = doc.add_paragraph("In Git Bash, enter this one command:")
    p.paragraph_format.keep_with_next = True
    add_code_block(doc, [
        "python src/inspect_orders.py",
    ])
    p = doc.add_paragraph("If Git Bash says that Python was not found, try:")
    p.paragraph_format.keep_with_next = True
    add_code_block(doc, ["py src/inspect_orders.py"])
    p = doc.add_paragraph("If neither command works, stop there and ask the group or instructor for help installing or locating Python. Do not edit the raw CSV to work around the error.")

    p = doc.add_paragraph("What the command means: ")
    p.add_run("python").bold = True
    p.add_run(" starts Python, and ")
    p.add_run("src/inspect_orders.py").bold = True
    p.add_run(" tells Python which file to run. The script then reads the CSV using a path that is relative to the project folder.")
    p.add_run("python").font.name = "Consolas"
    p.add_run(", try ")
    p.add_run("py src/inspect_orders.py").font.name = "Consolas"
    p.add_run(" instead.")

    doc.add_heading("Verified output", level=1)
    add_code_block(doc, [
        "File: data/bronze/orders/2026-07-12/orders.csv",
        "Rows: 104",
        "Columns: 9",
        "Column names: order_id, order_date, store_id, product_id, quantity,",
        "              unit_price, discount_pct, sales_channel, loyalty_member",
        "Order dates: 2026-07-12",
    ])

    doc.add_page_break()
    doc.add_heading("Raw-data storage convention", level=1)
    p = doc.add_paragraph(
        "Future daily order files should be preserved unchanged under the following pattern:"
    )
    p.paragraph_format.keep_with_next = True
    add_code_block(doc, ["data/bronze/orders/YYYY-MM-DD/orders.csv"])
    add_bullet(doc, "Use the date represented by the orders in the source file.")
    add_bullet(doc, "Create a separate dated directory for each daily pull.")
    add_bullet(doc, "Never edit or overwrite a file inside the raw directory.")
    add_bullet(doc, "Write future cleaned or transformed data to a different directory.")

    doc.add_heading("How the group can share these files", level=1)
    doc.add_paragraph(
        "Choose one person to be the uploader for this milestone. That person should enter the commands below one at a time in Git Bash. After each command, wait for it to finish. If an error appears, stop and ask for help instead of guessing."
    )
    upload_steps = [
        ("Check the current situation", ["git status"]),
        ("Create a separate branch for this work", ["git switch -c milestone-02"]),
        ("Tell Git which three milestone items to include", [
            "git add data/bronze/orders/2026-07-12/orders.csv",
            "git add src/inspect_orders.py",
            "git add docs/milestones/milestone_02.md",
        ]),
        ("Save the selected changes as a Git commit", [
            'git commit -m "Complete Milestone 02 orders capture"',
        ]),
        ("Send the branch to GitHub", ["git push -u origin milestone-02"]),
    ]
    for number, (label, commands) in enumerate(upload_steps, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(f"Step {number}: {label}")
        r.bold = True
        r.font.color.rgb = RGBColor.from_string(DARK_BLUE)
        add_code_block(doc, commands)

    doc.add_heading("What happens on GitHub", level=2)
    add_number(doc, "The uploader opens the Group 5 repository in a web browser.")
    add_number(doc, "GitHub should show a button to compare the new milestone-02 branch and create a pull request.")
    add_number(doc, "The uploader creates the pull request but does not merge it immediately.")
    add_number(doc, "At least one teammate reviews the Files changed tab and confirms that the raw CSV, Python script, and milestone note are present.")
    add_number(doc, "After the group agrees, the pull request can be merged into main.")

    doc.add_heading("How teammates receive the finished work", level=2)
    doc.add_paragraph(
        "After the pull request has been merged, each teammate opens Git Bash inside their own project folder and runs these commands one at a time:"
    )
    add_code_block(doc, ["git switch main", "git pull", "python src/inspect_orders.py"])
    doc.add_paragraph(
        "Their full computer path may be different from Caden's. That is expected. These commands work because they are run from inside each person's own copy of the repository."
    )

    doc.add_heading("Canvas submission checklist", level=1)
    checklist = [
        "Order date represented: 2026-07-12.",
        "Dataset size: 104 rows and 9 columns.",
        "Repository path: data/bronze/orders/2026-07-12/orders.csv.",
        "Screenshot or pasted output showing the inspection script ran successfully.",
        "Brief note explaining the dated raw-file storage convention.",
    ]
    for item in checklist:
        add_bullet(doc, f"[ ] {item}")

    doc.add_heading("Who should do what", level=1)
    add_bullet(doc, "Uploader: runs the Git commands, pushes the branch, and opens the pull request.")
    add_bullet(doc, "Reviewer: checks the three milestone additions on GitHub before the pull request is merged.")
    add_bullet(doc, "Tester: pulls the merged work and runs the Python script on a second computer.")
    add_bullet(doc, "Canvas submitter: submits the required facts and evidence after the group confirms everything is correct.")
    doc.add_paragraph("One person may fill more than one role, but assigning the roles clearly helps prevent duplicate or conflicting work.")

    warning = doc.add_table(rows=1, cols=1)
    set_table_geometry(warning, [9360])
    set_cell_shading(warning.cell(0, 0), "FFF4E5")
    p = warning.cell(0, 0).paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("Important: ")
    r.bold = True
    p.add_run("Nothing has been submitted to Canvas, committed, staged, or pushed. Late milestone submissions receive no credit, so the group should complete its review before July 15 at 11:59 PM.")

    doc.add_heading("Broader project connection", level=1)
    doc.add_paragraph(
        "This milestone establishes the raw-data foundation for later SQL loading, ingestion monitoring, weather enrichment, product entity resolution, and the final analytics-ready table. Preserving each daily source unchanged now prevents gaps and makes the later pipeline reproducible."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build_document()
