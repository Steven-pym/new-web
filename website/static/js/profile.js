document.addEventListener("DOMContentLoaded", function () {
    const fileInput = document.getElementById("file-input");
    const uploadLabel = document.querySelector(".upload-label");
    const uploadForm = document.querySelector(".file-upload");
    const progressBarContainer = document.getElementById("progress-bar-container");
    const progressBar = document.getElementById("progress-bar");

    // Drag-and-drop support
    uploadLabel.addEventListener("dragover", (event) => {
        event.preventDefault();
        uploadLabel.style.background = "#d1e7ff";
    });

    uploadLabel.addEventListener("dragleave", () => {
        uploadLabel.style.background = "#f8f9fa";
    });

    uploadLabel.addEventListener("drop", (event) => {
        event.preventDefault();
        fileInput.files = event.dataTransfer.files;
        uploadLabel.style.background = "#f8f9fa";
    });

    // Handle form submission with AJAX
    uploadForm.addEventListener("submit", function (event) {
        event.preventDefault();

        let formData = new FormData(uploadForm);
        let xhr = new XMLHttpRequest();
        xhr.open("POST", uploadForm.action, true);

        // Show progress bar
        progressBarContainer.style.display = "block";

        xhr.upload.onprogress = function (event) {
            if (event.lengthComputable) {
                let percent = (event.loaded / event.total) * 100;
                progressBar.style.width = percent + "%";
            }
        };

        xhr.onload = function () {
            if (xhr.status == 200) {
                location.reload(); // Refresh page on success
            }
        };

        xhr.send(formData);
    });
});

document.getElementById("profile-upload-form").addEventListener("submit", function(event) {
    event.preventDefault(); // Prevent default form submission

    let fileInput = document.getElementById("file-input");
    let file = fileInput.files[0];

    if (!file) {
        alert("Please select a file.");
        return;
    }

    let formData = new FormData();
    formData.append("file", file);

    let xhr = new XMLHttpRequest();
    xhr.open("POST", "{{ url_for('views.upload_profile') }}", true);

    // Progress bar handling
    xhr.upload.onprogress = function(event) {
        if (event.lengthComputable) {
            let percent = Math.round((event.loaded / event.total) * 100);
            document.getElementById("progress-bar").value = percent;
            document.getElementById("progress-text").textContent = percent + "%";
        }
    };

    xhr.onload = function() {
        if (xhr.status == 200) {
            location.reload(); // Refresh page on success
        } else {
            alert("Upload failed!");
        }
    };

    // Show progress indicator
    document.getElementById("upload-progress").style.display = "block";

    xhr.send(formData);
});

// slider
