// DOM Elements
const resultContainer = document.querySelector('.result-container');
const loading = document.getElementById('loading');
const fileInput = document.getElementById('fileInput');
const uploadButton = document.getElementById('uploadButton');
const uploadArea = document.querySelector('.upload-area');
const newPhoto = document.getElementById('newPhoto');

// Piece descriptions
const pieceDescriptions = {
    "junta_cria": "**Código:** 02RV-0512 **Descrição:** JUNTA CRIA 115FL X 302PS",
    "engrenagem_16dentes": "**Código:** 02RV-0043 **Descrição:** JCONJ MONT ENGRENAGEM 16 DENTES BI PARTIDA",
    "obstaculo_limpeza": "**Código:** 02RV-0098 **Descrição:** OBSTACULO DE LIMPEZA",
    "roda_bipartida": "**Código:** 02RV-0042 **Descrição:** CONJ MONT RODA GUIA BI PARTIDA"
};

// No camera support (upload-only)

// Helper: resize an image File to a maximum width/height and return a Blob (JPEG)
function resizeImageFile(file, maxWidth = 800, maxHeight = 800, quality = 0.7) {
    return new Promise((resolve, reject) => {
        if (!file || !file.type.startsWith('image/')) {
            return reject(new Error('Arquivo não é uma imagem'));
        }

        const reader = new FileReader();
        reader.onerror = (e) => reject(e);
        reader.onload = () => {
            const img = new Image();
            img.onerror = (e) => reject(e);
            img.onload = () => {
                let { width, height } = img;
                // calculate new dimensions while preserving aspect ratio
                if (width > maxWidth || height > maxHeight) {
                    const ratio = Math.min(maxWidth / width, maxHeight / height);
                    width = Math.round(width * ratio);
                    height = Math.round(height * ratio);
                }

                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                canvas.toBlob((blob) => {
                    if (blob) resolve(blob);
                    else reject(new Error('Erro ao gerar blob da imagem'));
                }, 'image/jpeg', quality);
            };
            img.src = reader.result;
        };
        reader.readAsDataURL(file);
    });
}

// Upload image to server
async function uploadImage(blob) {
    try {
        const formData = new FormData();
        formData.append('photo', blob, 'photo.jpg');
        
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.result_image) {
            // The result image is no longer displayed, but we still get piece info
            showResult(data);
        } else {
            throw new Error('Invalid server response');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', 'Error processing image: ' + error.message);
    } finally {
        loading.style.display = 'none';
    }
}

// Show result image and piece information
function showResult(data) {
    // Display piece description if available
    const pieceDescription = document.getElementById('piece-description');
    if (data && data.detected_piece) {
        console.log("Peça detectada:", data.detected_piece); // Debug log
        const normalizedPieceName = data.detected_piece.toLowerCase().replace(/\s+/g, '_');
        if (pieceDescriptions[normalizedPieceName]) {
            // Convert markdown-style bold to HTML
            let description = pieceDescriptions[normalizedPieceName].replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            // Add confidence percentage
            const confidence = data.confidence ? `<div class="mt-2"><strong>Confiança da Detecção:</strong> ${(data.confidence * 100).toFixed(1)}%</div>` : '';
            pieceDescription.innerHTML = description + confidence;
        } else {
            console.log("Peça não encontrada no dicionário:", normalizedPieceName); // Debug log
            const confidence = data.confidence ? `<br>Confiança da Detecção: ${(data.confidence * 100).toFixed(1)}%` : '';
            pieceDescription.innerHTML = `Peça detectada: ${data.detected_piece}${confidence}`;
        }

        // Se o servidor retornou dados do inventário, mostra quantidade e status
        if (data.part) {
            const q = data.part.quantity;
            const inStock = data.part.in_stock;
            const statusBadge = inStock ? `<span class="badge bg-success ms-2">Em estoque</span>` : `<span class="badge bg-danger ms-2">Sem estoque</span>`;
            const inventoryInfo = `<div class="mt-2"><strong>Quantidade no inventário:</strong> ${q} ${statusBadge}</div>`;
            pieceDescription.innerHTML += inventoryInfo;
        }
    } else {
        pieceDescription.innerHTML = 'Nenhuma peça detectada';
    }
    
    // If server returned an annotated image, display it
    const resultImg = document.getElementById('result-img');
    if (data && data.result_image && resultImg) {
        let src = data.result_image;

        // If it's already a data URL, use it
        if (src.startsWith('data:')) {
            // fine
        } else if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('/')) {
            // absolute or root-relative URL - use as-is
        } else if (src.startsWith('static/')) {
            // relative static path from server, ensure leading slash
            src = '/' + src;
        } else {
            // assume plain base64 and prefix data URL header
            src = 'data:image/jpeg;base64,' + src;
        }

        // Append cache-buster for URLs (so overwritten files are re-fetched)
        if (src.startsWith('/') || src.startsWith('http://') || src.startsWith('https://')) {
            const sep = src.includes('?') ? '&' : '?';
            resultImg.src = src + sep + 'cb=' + Date.now();
        } else {
            resultImg.src = src;
        }
        resultImg.style.display = 'block';
    } else if (resultImg) {
        resultImg.style.display = 'none';
        resultImg.src = '';
    }

    resultContainer.style.display = 'block';
}

// Show alert message
function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.card'));
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Event Listeners
uploadButton.addEventListener('click', () => fileInput.click());

// New Photo button: clear result and show upload controls again
if (newPhoto) {
    newPhoto.addEventListener('click', () => {
        if (resultContainer) resultContainer.style.display = 'none';
        const resultImg = document.getElementById('result-img');
        if (resultImg) {
            resultImg.style.display = 'none';
            resultImg.src = '';
        }
        const pieceDescription = document.getElementById('piece-description');
        if (pieceDescription) pieceDescription.innerHTML = '';
        // ensure upload button is visible
        if (uploadButton) uploadButton.style.display = 'inline-block';
    });
}

fileInput.addEventListener('change', async (e) => {
    if (e.target.files && e.target.files[0]) {
        loading.style.display = 'flex';
        const file = e.target.files[0];
        try {
            const resized = await resizeImageFile(file, 800, 800, 0.7);
            await uploadImage(resized);
        } catch (err) {
            console.error('Erro ao redimensionar/enviar imagem:', err);
            showAlert('danger', 'Erro ao processar a imagem antes do envio.');
        } finally {
            fileInput.value = '';
        }
    }
});

// Drag and drop functionality
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('border-success');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('border-success');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('border-success');
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        loading.style.display = 'flex';
        const file = e.dataTransfer.files[0];
    resizeImageFile(file, 800, 800, 0.7)
            .then(resized => uploadImage(resized))
            .catch(err => {
                console.error('Erro ao redimensionar/enviar imagem (drop):', err);
                showAlert('danger', 'Erro ao processar a imagem antes do envio.');
            });
    }
});

// No camera functions to expose (upload-only)
