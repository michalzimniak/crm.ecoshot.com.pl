/**
 * Photos View - Zarządzanie zdjęciami
 */

import { photosAPI, galleriesAPI } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { confirmDialog } from '../confirm.js';

let currentGallery = null;
let selectedPhotos = [];

export async function renderPhotos(params) {
    const container = document.getElementById('viewContainer');
    
    // Get gallery_id from URL
    const urlParams = new URLSearchParams(window.location.hash.split('?')[1]);
    const galleryId = urlParams.get('gallery');
    
    if (!galleryId) {
        showToast('Brak ID galerii', 'danger');
        navigate('/galleries');
        return;
    }
    
    // Show loading
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-camera"></i> Zdjęcia</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        // Load gallery info
        const galleryResponse = await galleriesAPI.getById(galleryId);
        currentGallery = galleryResponse.data;
        
        // Load photos
        const photosResponse = await photosAPI.getAll({ gallery_id: galleryId });
        const photos = photosResponse.data || [];
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-camera"></i> Zdjęcia: ${currentGallery.name}</h1>
                    <p class="text-muted mb-0">${photos.length} zdjęć</p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-success" onclick="showUploadModal()">
                        <i class="bi bi-upload"></i> Dodaj zdjęcia
                    </button>
                    ${selectedPhotos.length > 0 ? `
                        <button class="btn btn-danger" onclick="deleteSelectedPhotos()">
                            <i class="bi bi-trash"></i> Usuń zaznaczone (${selectedPhotos.length})
                        </button>
                    ` : ''}
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/galleries/${galleryId}'">
                        <i class="bi bi-arrow-left"></i> Galeria
                    </button>
                </div>
            </div>
            
            <!-- Photos Grid -->
            ${photos.length === 0 ? `
                <div class="card">
                    <div class="card-body text-center py-5">
                        <i class="bi bi-images display-1 text-muted"></i>
                        <p class="text-muted mt-3">Brak zdjęć</p>
                        <button class="btn btn-success" onclick="showUploadModal()">
                            <i class="bi bi-upload"></i> Dodaj pierwsze zdjęcie
                        </button>
                    </div>
                </div>
            ` : `
                <div class="row g-3">
                    ${photos.map(photo => `
                        <div class="col-md-3 col-lg-2">
                            <div class="card photo-card ${selectedPhotos.includes(photo.id) ? 'selected' : ''}" 
                                 data-photo-id="${photo.id}">
                                <div class="position-relative">
                                    <img src="/api/photos/${photo.id}/download?version=thumbnail" 
                                         class="card-img-top" 
                                         alt="${photo.filename}"
                                         onclick="viewPhoto(${photo.id})"
                                         style="cursor: pointer; aspect-ratio: 1; object-fit: cover;">
                                    <div class="position-absolute top-0 start-0 p-2">
                                        <input type="checkbox" class="form-check-input photo-select" 
                                               data-photo-id="${photo.id}"
                                               ${selectedPhotos.includes(photo.id) ? 'checked' : ''}>
                                    </div>
                                    ${photo.is_selected ? `
                                        <div class="position-absolute top-0 end-0 p-2">
                                            <i class="bi bi-heart-fill text-danger"></i>
                                        </div>
                                    ` : ''}
                                </div>
                                <div class="card-body p-2">
                                    <small class="text-muted d-block text-truncate">${photo.filename}</small>
                                    <small class="text-muted">#${photo.sequence_number || photo.id}</small>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `}
            
            <!-- Upload Modal -->
            <div class="modal fade" id="uploadModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Dodaj zdjęcia</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Wybierz pliki</label>
                                <input type="file" class="form-control" id="photoFiles" 
                                       accept="image/*" multiple>
                                <small class="text-muted">Akceptowane formaty: JPG, PNG, WebP</small>
                            </div>
                            <div id="uploadPreview" class="row g-2 mt-3"></div>
                            <div id="uploadProgress" class="mt-3" style="display: none;">
                                <div class="progress">
                                    <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Anuluj</button>
                            <button type="button" class="btn btn-success" onclick="uploadPhotos()">
                                <i class="bi bi-upload"></i> Prześlij
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Photo View Modal -->
            <div class="modal fade" id="photoModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="photoModalTitle">Zdjęcie</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center" id="photoModalBody">
                            <div class="spinner-border text-success" role="status"></div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-danger" onclick="deleteCurrentPhoto()">
                                <i class="bi bi-trash"></i> Usuń
                            </button>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Zamknij</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        setupPhotosListeners();
        
    } catch (error) {
        console.error('Failed to load photos:', error);
        showToast('Błąd ładowania zdjęć', 'danger');
        navigate('/galleries');
    }
}

function setupPhotosListeners() {
    // Photo selection checkboxes
    document.querySelectorAll('.photo-select').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const photoId = parseInt(e.target.dataset.photoId);
            if (e.target.checked) {
                if (!selectedPhotos.includes(photoId)) {
                    selectedPhotos.push(photoId);
                }
            } else {
                selectedPhotos = selectedPhotos.filter(id => id !== photoId);
            }
            
            // Update UI
            const card = document.querySelector(`[data-photo-id="${photoId}"]`);
            if (card) {
                card.classList.toggle('selected', e.target.checked);
            }
            
            // Re-render to show delete button
            renderPhotos();
        });
    });
    
    // File input change
    const fileInput = document.getElementById('photoFiles');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            showUploadPreview(files);
        });
    }
}

function showUploadPreview(files) {
    const preview = document.getElementById('uploadPreview');
    preview.innerHTML = '';
    
    files.forEach(file => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const col = document.createElement('div');
            col.className = 'col-md-3';
            col.innerHTML = `
                <div class="card">
                    <img src="${e.target.result}" class="card-img-top" alt="${file.name}">
                    <div class="card-body p-2">
                        <small class="text-truncate d-block">${file.name}</small>
                    </div>
                </div>
            `;
            preview.appendChild(col);
        };
        reader.readAsDataURL(file);
    });
}

window.showUploadModal = () => {
    const modal = new bootstrap.Modal(document.getElementById('uploadModal'));
    modal.show();
};

window.uploadPhotos = async () => {
    const fileInput = document.getElementById('photoFiles');
    const files = fileInput.files;
    
    if (files.length === 0) {
        showToast('Wybierz pliki', 'warning');
        return;
    }
    
    const progressContainer = document.getElementById('uploadProgress');
    const progressBar = progressContainer.querySelector('.progress-bar');
    progressContainer.style.display = 'block';
    
    try {
        let uploaded = 0;
        
        for (let file of files) {
            const formData = new FormData();
            formData.append('files', file);
            formData.append('gallery_id', currentGallery.id);
            
            await photosAPI.upload(formData);
            uploaded++;
            
            const percent = (uploaded / files.length) * 100;
            progressBar.style.width = `${percent}%`;
        }
        
        showToast(`Przesłano ${uploaded} zdjęć`, 'success');
        
        // Close modal and refresh
        const modal = bootstrap.Modal.getInstance(document.getElementById('uploadModal'));
        modal.hide();
        
        // Reset
        fileInput.value = '';
        document.getElementById('uploadPreview').innerHTML = '';
        progressContainer.style.display = 'none';
        progressBar.style.width = '0%';
        
        renderPhotos();
        
    } catch (error) {
        console.error('Failed to upload photos:', error);
        progressContainer.style.display = 'none';
    }
};

let currentPhotoId = null;

window.viewPhoto = async (photoId) => {
    currentPhotoId = photoId;
    
    try {
        const response = await photosAPI.getById(photoId);
        const photo = response.data;
        
        const modalTitle = document.getElementById('photoModalTitle');
        const modalBody = document.getElementById('photoModalBody');
        
        modalTitle.textContent = photo.filename;
        modalBody.innerHTML = `
            <img src="/api/photos/${photo.id}/download?version=watermarked" 
                 class="img-fluid" 
                 alt="${photo.filename}">
            <div class="mt-3 text-start">
                <p><strong>Kolejność:</strong> #${photo.display_order ?? photo.id}</p>
                <p><strong>Plik:</strong> ${photo.filename}</p>
                ${photo.is_selected ? '<p class="text-danger"><i class="bi bi-heart-fill"></i> Wybrane przez klienta</p>' : ''}
            </div>
        `;
        
        const modal = new bootstrap.Modal(document.getElementById('photoModal'));
        modal.show();
        
    } catch (error) {
        console.error('Failed to load photo:', error);
        showToast('Błąd ładowania zdjęcia', 'danger');
    }
};

window.deleteCurrentPhoto = async () => {
    if (!currentPhotoId) return;

    const ok = await confirmDialog({
        title: 'Usuń zdjęcie',
        message: 'Czy na pewno chcesz usunąć to zdjęcie?',
        confirmText: 'Usuń',
        cancelText: 'Anuluj',
        danger: true,
    });
    if (!ok) return;
    
    try {
        await photosAPI.delete(currentPhotoId);
        showToast('Zdjęcie usunięte', 'success');
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('photoModal'));
        modal.hide();
        
        // Refresh
        currentPhotoId = null;
        renderPhotos();
        
    } catch (error) {
        console.error('Failed to delete photo:', error);
    }
};

window.deleteSelectedPhotos = async () => {
    if (selectedPhotos.length === 0) return;

    const ok = await confirmDialog({
        title: 'Usuń zdjęcia',
        message: `Czy na pewno chcesz usunąć ${selectedPhotos.length} zdjęć?`,
        confirmText: 'Usuń',
        cancelText: 'Anuluj',
        danger: true,
    });
    if (!ok) return;
    
    try {
        for (let photoId of selectedPhotos) {
            await photosAPI.delete(photoId);
        }
        
        showToast(`Usunięto ${selectedPhotos.length} zdjęć`, 'success');
        selectedPhotos = [];
        renderPhotos();
        
    } catch (error) {
        console.error('Failed to delete photos:', error);
    }
};
