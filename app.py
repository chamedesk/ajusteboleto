from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import os
import uuid
import traceback
import fitz
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ajuste-foto-boleto-web-v2"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def ajustar_pdf(input_path, left=5, top=5, right=15, bottom=5, only_meter_images=True):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_name = f"{base_name}_AJUSTADO.pdf"
    output_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4().hex}_{output_name}")

    doc = fitz.open(input_path)
    total_changes = 0

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)

        if not images:
            continue

        page_width = page.rect.width
        page_height = page.rect.height

        for img in images:
            xref = img[0]
            rects = page.get_image_rects(xref)

            for rect in rects:
                if rect.width < 40 or rect.height < 30:
                    continue

                if rect.width > page_width * 0.85 or rect.height > page_height * 0.85:
                    continue

                if only_meter_images:
                    if rect.x0 > page_width * 0.45:
                        continue
                    if rect.y0 < page_height * 0.10 or rect.y1 > page_height * 0.76:
                        continue

                new_rect = fitz.Rect(
                    max(0, rect.x0 - left),
                    max(0, rect.y0 - top),
                    min(page_width, rect.x1 + right),
                    min(page_height, rect.y1 + bottom),
                )

                if abs(new_rect.width - rect.width) < 3 and abs(new_rect.height - rect.height) < 3:
                    continue

                pix = fitz.Pixmap(doc, xref)
                page.insert_image(new_rect, pixmap=pix, overlay=True)
                total_changes += 1
                pix = None

    if total_changes == 0:
        doc.close()
        raise RuntimeError(
            "Nenhuma foto foi ajustada automaticamente. "
            "Tente desmarcar a opção de ajustar somente fotos dos hidrômetros."
        )

    doc.save(output_path)
    doc.close()
    return output_path, total_changes


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            pdf = request.files.get("pdf")
            if not pdf or not pdf.filename.lower().endswith(".pdf"):
                flash("Selecione um arquivo PDF válido.")
                return redirect(url_for("index"))

            left = float(request.form.get("left", 5))
            top = float(request.form.get("top", 5))
            right = float(request.form.get("right", 15))
            bottom = float(request.form.get("bottom", 5))
            only_meter_images = request.form.get("only_meter_images") == "on"

            safe_name = secure_filename(pdf.filename)
            file_id = uuid.uuid4().hex
            input_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")
            pdf.save(input_path)

            output_path, total_changes = ajustar_pdf(
                input_path=input_path,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                only_meter_images=only_meter_images,
            )

            return send_file(
                output_path,
                as_attachment=True,
                download_name=os.path.basename(output_path),
                mimetype="application/pdf"
            )

        except Exception as e:
            print("ERRO AO PROCESSAR PDF:")
            traceback.print_exc()
            flash(f"Erro ao processar PDF: {str(e)}")
            return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.errorhandler(413)
def too_large(e):
    flash("O PDF é muito grande. Envie um arquivo menor que 50 MB.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
