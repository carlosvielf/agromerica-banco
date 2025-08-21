from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
import os
from werkzeug.utils import secure_filename
import logging
from datetime import datetime
from models import db, ImageRecord, Part
from ultralytics import YOLO
import cv2
import json

# Configuração do Flask
app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Limite de 16MB para upload
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# Usa caminho absoluto para evitar problemas com paths relativos/permissões
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'image_history.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
with app.app_context():
    try:
        # Garante que o diretório 'instance' exista e seja gravável
        instance_dir = os.path.join(BASE_DIR, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        # Ajusta permissões se necessário (mantém permissões do usuário se já existirem)
        try:
            os.chmod(instance_dir, 0o775)
        except Exception:
            # Se a mudança de permissões falhar, não interrompe; apenas prossegue
            pass

        db.create_all()
    except Exception as e:
        logging.critical(f"ERRO FATAL: Não foi possível criar o banco de dados em '{app.config['SQLALCHEMY_DATABASE_URI']}'.")
        logging.critical(f"Motivo: {e}")
        logging.critical("Por favor, verifique as permissões de escrita no diretório do projeto.")
        raise

# Carrega o modelo YOLO
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'best.pt')
model = YOLO(MODEL_PATH)
model.to('cpu')

# Configuração dos diretórios
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
RESULTS_FOLDER = os.path.join(BASE_DIR, 'static', 'results')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Seed: garante que peças conhecidas pelo modelo existam no inventário
with app.app_context():
    try:
        seed_name = 'junta_cria'
        if not Part.query.filter_by(name=seed_name).first():
            seed_part = Part(name=seed_name, quantity=0)
            db.session.add(seed_part)
            db.session.commit()
            logger.info(f"Peça seed inserida no DB: {seed_name}")
    except Exception as e:
        logger.warning(f"Não foi possível inserir seed de peças: {e}")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(image_path):
    """
    Processa a imagem usando YOLO, salva o resultado e retorna informações.
    """
    try:
        logger.info(f"Iniciando processamento da imagem: {image_path}")
        results = model.predict(source=image_path, conf=0.25, device='cpu')

        # CORREÇÃO: Verifica se a lista de resultados não está vazia para evitar IndexError.
        if not results or len(results) == 0:
            logger.warning("Modelo não retornou resultados para a imagem.")
            return None, None, None, None

        result = results[0]
        annotated_img = result.plot()

        output_filename = f"processed_{os.path.basename(image_path)}"
        output_path = os.path.join(RESULTS_FOLDER, output_filename)
        cv2.imwrite(output_path, annotated_img)
        logger.info(f"Imagem processada e salva em: {output_path}")

        detected_piece = None
        highest_confidence = 0.0
        # Converte o resultado JSON para um objeto Python (dicionário/lista)
        detection_details = json.loads(result.tojson())

        if len(result.boxes) > 0:
            best_box = max(result.boxes, key=lambda box: box.conf[0])
            class_id = int(best_box.cls[0].cpu())
            detected_piece = result.names[class_id]
            highest_confidence = float(best_box.conf[0].cpu())
            logger.info(f"Peça com maior confiança: {detected_piece} ({highest_confidence:.2f})")

        return output_path, detection_details, detected_piece, highest_confidence
    # MELHORIA: Captura exceções de forma mais específica se necessário, mas Exception geral é ok aqui.
    except Exception as e:
        logger.error(f"Erro ao processar imagem com YOLO: {e}", exc_info=True)
        return None, None, None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'photo' not in request.files:
        return jsonify({'error': 'Nenhuma foto enviada'}), 400
    
    file = request.files['photo']
    
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de arquivo não permitido'}), 400

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"image_{timestamp}_{secure_filename(file.filename)}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    
    file.save(file_path)
    logger.info(f"Imagem salva em: {file_path}")

    # MELHORIA: Bloco try/except para garantir que o arquivo seja removido em caso de falha no processamento.
    try:
        result_path, detection_details, detected_piece, confidence = process_image(file_path)
        
        if result_path is None:
            # Se o processamento falhar, remove o arquivo original para evitar lixo.
            os.remove(file_path)
            logger.warning(f"Arquivo removido devido a falha no processamento: {file_path}")
            return jsonify({'error': 'Erro ao processar imagem'}), 500

        if detected_piece:
            # Normaliza o nome retornado pelo modelo para buscar no DB
            normalized_name = detected_piece.strip().lower().replace(' ', '_')
            part = Part.query.filter_by(name=normalized_name).first()
            if not part:
                # Cria a peça no inventário com quantity=0 (não altera automaticamente estoque)
                part = Part(name=normalized_name, quantity=0)
                db.session.add(part)
                db.session.commit()
                logger.info(f"Peça criada no inventário (quantity=0): {normalized_name}")
            # NÃO incrementa automaticamente a quantidade — o usuário controla o estoque
            detected_piece = normalized_name
        
        # CORREÇÃO: Converte o objeto Python de volta para uma string JSON antes de salvar no DB.
        detection_results_str = json.dumps(detection_details) if detection_details else None

        # Caminhos relativos para o banco de dados
        original_path_relative = os.path.join('static', 'uploads', filename)
        processed_path_relative = os.path.join('static', 'results', os.path.basename(result_path))

        image_record = ImageRecord(
            original_image_path=original_path_relative.replace('\\', '/'),
            processed_image_path=processed_path_relative.replace('\\', '/'),
            filename=filename,
            detection_results=detection_results_str
        )
        db.session.add(image_record)
        db.session.commit()
        
        # CORREÇÃO: Usa url_for para gerar a URL de forma segura e portável.
        result_url = url_for('serve_static', filename=f"results/{os.path.basename(result_path)}")

        # Inclui informações do inventário da peça na resposta (se houver)
        part_info = None
        if detected_piece:
            try:
                # busca a peça atualizada no DB
                part_db = Part.query.filter_by(name=detected_piece).first()
                if part_db:
                    part_info = {
                        'name': part_db.name,
                        'quantity': part_db.quantity,
                        'in_stock': bool(part_db.quantity and part_db.quantity > 0)
                    }
            except Exception as e:
                logger.warning(f"Não foi possível recuperar info da peça do DB: {e}")

        return jsonify({
            'result_image': result_url,
            'detected_piece': detected_piece,
            'confidence': confidence,
            'part': part_info
        })

    except Exception as e:
        logger.error(f"Erro crítico no pipeline de upload: {str(e)}", exc_info=True)
        # Garante a remoção do arquivo original em caso de erro inesperado.
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': 'Ocorreu um erro interno no servidor.'}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    # O send_from_directory já lida com a junção de caminhos de forma segura.
    return send_from_directory('static', filename)

@app.route('/image/<int:image_id>')
def image_details(image_id):
    image = ImageRecord.query.get_or_404(image_id)
    parts = Part.query.order_by(Part.name).all()
    return render_template('image_details.html', image=image, parts=parts)

@app.route('/image/<int:image_id>/delete', methods=['POST'])
def delete_image(image_id):
    image = ImageRecord.query.get_or_404(image_id)
    
    try:
        # Reconstrói o caminho absoluto para os arquivos no disco.
        original_path_full = os.path.join(BASE_DIR, image.original_image_path)
        processed_path_full = os.path.join(BASE_DIR, image.processed_image_path)
        
        if os.path.exists(original_path_full):
            os.remove(original_path_full)
        if os.path.exists(processed_path_full):
            os.remove(processed_path_full)
    except Exception as e:
        logger.error(f"Erro ao deletar arquivos de imagem do disco: {str(e)}")
    
    db.session.delete(image)
    db.session.commit()
    
    return redirect(url_for('index'))


@app.route('/part/<int:part_id>/update', methods=['POST'])
def update_part_quantity(part_id):
    """Atualiza a quantidade da peça (formulário simples vindo de image_details)."""
    part = Part.query.get_or_404(part_id)
    try:
        qty = request.form.get('quantity', None)
        if qty is None:
            return jsonify({'error': 'Quantidade não fornecida'}), 400

        # Tenta converter para inteiro e valida
        try:
            qty_int = int(qty)
            if qty_int < 0:
                return jsonify({'error': 'Quantidade inválida'}), 400
        except ValueError:
            return jsonify({'error': 'Quantidade inválida'}), 400

        part.quantity = qty_int
        db.session.commit()

        # Se a requisição veio de um form normal (não-AJAX), redireciona de volta
        ref = request.referrer
        if ref:
            return redirect(ref)

        return jsonify({'success': True, 'part': {'id': part.id, 'name': part.name, 'quantity': part.quantity}})
    except Exception as e:
        logger.error(f"Erro ao atualizar quantidade da peça: {e}")
        return jsonify({'error': 'Erro interno'}), 500

if __name__ == '__main__':
    logger.info("Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=5052, debug=True)