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

function deleteSpecialization(specializationId) {
    if (!confirm('Are you sure you want to delete this specialization?')) {
        return;
    }

    const csrftoken = getCookie('csrftoken');
    
    fetch(`/admin/gym_app/specialization/${specializationId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        // Reload the page after successful deletion
        window.location.reload();
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error deleting specialization. It might be in use by trainers.');
    });
}
