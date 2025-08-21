from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
import logging
from datetime import datetime
from ultralytics import YOLO
import cv2
import numpy as np
from PIL import Image

# Configuração do Flask
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB para upload

# Configuração dos diretórios
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
RESULTS_FOLDER = os.path.join(BASE_DIR, 'static', 'results')

# Criação dos diretórios se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Extensões permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Carrega o modelo YOLO (apenas uma vez)
try:
    logger.info("Iniciando carregamento do modelo YOLO...")
    model = YOLO('best.pt')
    # Força o uso da CPU
    model.to('cpu')
    logger.info("Modelo YOLO carregado com sucesso!")
except Exception as e:
    logger.error(f"Erro ao carregar o modelo YOLO: {str(e)}")
    model = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(image_path):
    """
    Processa a imagem usando YOLOv8 e retorna o caminho da imagem com as detecções
    """
    try:
        if model is None:
            raise Exception("Modelo YOLO não foi carregado corretamente")

        logger.info(f"Iniciando processamento da imagem: {image_path}")
        
        # Realiza a predição forçando CPU
        results = model.predict(
            source=image_path,
            device='cpu',
            conf=0.25  # threshold de confiança
        )
        
        # Obtém o primeiro resultado
        result = results[0]
        
        # Carrega a imagem original
        img = cv2.imread(image_path)
        if img is None:
            raise Exception("Não foi possível carregar a imagem")
        
        logger.info(f"Detectados {len(result.boxes)} objetos")
        
        # Para cada detecção
        for box in result.boxes:
            # Coordenadas do box
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            
            # Classe e confiança
            cls = int(box.cls[0].cpu().numpy())
            conf = float(box.conf[0].cpu().numpy())
            
            # Nome da classe
            class_name = result.names[cls]
            
            # Desenha o retângulo
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Adiciona o texto
            label = f'{class_name} {conf:.2f}'
            cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, (0, 255, 0), 2)

        # Salva a imagem processada
        output_path = os.path.join(RESULTS_FOLDER, f"detected_{os.path.basename(image_path)}")
        cv2.imwrite(output_path, img)
        
        logger.info(f"Imagem processada salva em: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Erro ao processar imagem com YOLO: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'Nenhuma foto enviada'}), 400
        
        file = request.files['photo']
        
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de arquivo não permitido'}), 400

        # Gera um nome único para o arquivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"image_{timestamp}_{secure_filename(file.filename)}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Salva o arquivo
        file.save(file_path)
        logger.info(f"Imagem salva em: {file_path}")

        # Processa a imagem com YOLO
        result_path = process_image(file_path)
        
        if result_path is None:
            return jsonify({'error': 'Erro ao processar imagem'}), 500

        # Retorna o caminho relativo para o frontend
        result_url = '/'.join(['static', 'results', os.path.basename(result_path)])
        return jsonify({'result_image': result_url})

    except Exception as e:
        logger.error(f"Erro no upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    if model is None:
        logger.error("Erro: Modelo YOLO não foi carregado. Verifique se o arquivo 'best.pt' existe.")
    else:
        logger.info("Servidor iniciando com modelo YOLO carregado!")
    app.run(host='0.0.0.0', port=5051, debug=False)  # debug=False para evitar carregar o modelo duas vezes
