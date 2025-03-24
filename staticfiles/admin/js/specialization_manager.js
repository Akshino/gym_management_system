document.addEventListener('DOMContentLoaded', function() {
    // Get the modal
    const modal = document.getElementById('specializationModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    
    // Get the <span> element that closes the modal
    const span = document.getElementsByClassName('close')[0];
    
    // When the user clicks on <span> (x), close the modal
    span.onclick = function() {
        modal.style.display = 'none';
    }
    
    // When the user clicks anywhere outside of the modal, close it
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function openSpecializationModal(action) {
    const modal = document.getElementById('specializationModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    const selectedSpecId = document.querySelector('select[name="specialization"]').value;

    modalBody.innerHTML = '';
    modal.style.display = 'block';

    switch(action) {
        case 'add':
            modalTitle.textContent = 'Add New Specialization';
            modalBody.innerHTML = `
                <form id="addSpecForm">
                    <div class="form-group">
                        <label for="specName">Name:</label>
                        <input type="text" id="specName" name="name" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" name="is_active" checked> Active
                        </label>
                    </div>
                    <button type="submit" class="btn btn-primary">Add Specialization</button>
                </form>
            `;
            document.getElementById('addSpecForm').onsubmit = function(e) {
                e.preventDefault();
                addSpecialization();
            };
            break;

        case 'edit':
            if (!selectedSpecId) {
                alert('Please select a specialization to edit');
                modal.style.display = 'none';
                return;
            }
            modalTitle.textContent = 'Edit Specialization';
            fetchSpecializationDetails(selectedSpecId, function(spec) {
                modalBody.innerHTML = `
                    <form id="editSpecForm">
                        <div class="form-group">
                            <label for="specName">Name:</label>
                            <input type="text" id="specName" name="name" class="form-control" value="${spec.name}" required>
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" name="is_active" ${spec.is_active ? 'checked' : ''}> Active
                            </label>
                        </div>
                        <button type="submit" class="btn btn-primary">Update Specialization</button>
                    </form>
                `;
                document.getElementById('editSpecForm').onsubmit = function(e) {
                    e.preventDefault();
                    updateSpecialization(selectedSpecId);
                };
            });
            break;

        case 'view':
            if (!selectedSpecId) {
                alert('Please select a specialization to view');
                modal.style.display = 'none';
                return;
            }
            modalTitle.textContent = 'View Specialization';
            fetchSpecializationDetails(selectedSpecId, function(spec) {
                modalBody.innerHTML = `
                    <div class="spec-details">
                        <p><strong>Name:</strong> ${spec.name}</p>
                        <p><strong>Status:</strong> ${spec.is_active ? 'Active' : 'Inactive'}</p>
                    </div>
                `;
            });
            break;

        case 'delete':
            if (!selectedSpecId) {
                alert('Please select a specialization to delete');
                modal.style.display = 'none';
                return;
            }
            modalTitle.textContent = 'Delete Specialization';
            modalBody.innerHTML = `
                <p>Are you sure you want to delete this specialization?</p>
                <div class="button-group">
                    <button onclick="deleteSpecialization(${selectedSpecId})" class="btn btn-danger">Yes, Delete</button>
                    <button onclick="document.getElementById('specializationModal').style.display='none'" class="btn btn-secondary">Cancel</button>
                </div>
            `;
            break;
    }
}

function fetchSpecializationDetails(id, callback) {
    fetch(`/admin/gym_app/specialization/${id}/`)
        .then(response => response.json())
        .then(data => callback(data))
        .catch(error => {
            console.error('Error:', error);
            alert('Error fetching specialization details');
        });
}

function addSpecialization() {
    const form = document.getElementById('addSpecForm');
    const data = {
        name: form.querySelector('[name="name"]').value,
        is_active: form.querySelector('[name="is_active"]').checked
    };

    fetch('/admin/gym_app/specialization/add/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const select = document.querySelector('select[name="specialization"]');
            const option = new Option(data.name, data.id);
            select.add(option);
            select.value = data.id;
            document.getElementById('specializationModal').style.display = 'none';
        } else {
            alert(data.error || 'Error adding specialization');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding specialization');
    });
}

function updateSpecialization(id) {
    const form = document.getElementById('editSpecForm');
    const data = {
        name: form.querySelector('[name="name"]').value,
        is_active: form.querySelector('[name="is_active"]').checked
    };

    fetch(`/admin/gym_app/specialization/${id}/change/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const select = document.querySelector('select[name="specialization"]');
            const option = select.querySelector(`option[value="${id}"]`);
            option.textContent = data.name;
            document.getElementById('specializationModal').style.display = 'none';
        } else {
            alert(data.error || 'Error updating specialization');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating specialization');
    });
}

function deleteSpecialization(id) {
    fetch(`/admin/gym_app/specialization/${id}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const select = document.querySelector('select[name="specialization"]');
            const option = select.querySelector(`option[value="${id}"]`);
            option.remove();
            document.getElementById('specializationModal').style.display = 'none';
        } else {
            alert(data.error || 'Error deleting specialization');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error deleting specialization');
    });
}
