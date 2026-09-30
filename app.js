const API_BASE_URL = "http://127.0.0.1:8000";

function toggleAuth() {
    const loginBox = document.getElementById('login-box');
    const registerBox = document.getElementById('register-box');
    const msg = document.getElementById('auth-message');

    msg.innerText = "";
    if (loginBox.style.display === "none") {
        loginBox.style.display = "block";
        registerBox.style.display = "none";
    } else {
        loginBox.style.display = "none";
        registerBox.style.display = "block";
    }
}


async function register() {
    const name = document.getElementById('reg-name').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const msg = document.getElementById('auth-message');

    try {
        const response = await fetch(`${API_BASE_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: name, email: email, password: password })
        });

        const data = await response.json();
        if (response.ok) {
            msg.style.color = "green";
            msg.innerText = "Registration successful! You can login now.";
            toggleAuth(); // Switch back to login
        } else {
            msg.style.color = "red";
            msg.innerText = data.detail || "Registration failed.";
        }
    } catch (error) {
        msg.innerText = "Server connection error.";
    }
}

// Login user
async function login() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const msg = document.getElementById('auth-message');

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, password: password })
        });

        const data = await response.json();
        if (response.ok) {

            localStorage.setItem('token', data.access_token);
            localStorage.setItem('user_id', data.user.id);


            document.getElementById('auth-section').style.display = 'none';
            document.getElementById('dashboard-section').style.display = 'block';
        } else {
            msg.style.color = "red";
            msg.innerText = data.detail || "Invalid email or password.";
        }
    } catch (error) {
        msg.innerText = "Server connection error.";
    }
}

// Logout function
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('resume_id');
    document.getElementById('dashboard-section').style.display = 'none';
    document.getElementById('auth-section').style.display = 'block';

    // Reset fields
    document.getElementById('results-area').style.display = 'none';
    document.getElementById('action-buttons').style.display = 'none';
    document.getElementById('extra-results-area').innerHTML = '';
    document.getElementById('resume-file').value = "";
    document.getElementById('dashboard-message').innerText = "";
}

// Upload and Analyze Resume
async function uploadAndAnalyze() {
    const fileInput = document.getElementById('resume-file');
    const msg = document.getElementById('dashboard-message');
    const uploadBtn = document.getElementById('upload-btn');
    const userId = localStorage.getItem('user_id');

    if (fileInput.files.length === 0) {
        msg.style.color = "red";
        msg.innerText = "Please select a file first.";
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
        uploadBtn.disabled = true;
        msg.style.color = "blue";
        msg.innerText = "Uploading file... Please wait.";

        // 1. Upload API Call
        const uploadResponse = await fetch(`${API_BASE_URL}/upload-resume?user_id=${userId}`, {
            method: 'POST',
            body: formData
        });

        const uploadData = await uploadResponse.json();

        if (!uploadResponse.ok) {
            throw new Error(uploadData.detail || "Upload failed");
        }

        const resumeId = uploadData.resume_id;
        localStorage.setItem('resume_id', resumeId);
        msg.innerText = "File uploaded successfully! AI is analyzing it now... (This may take a few seconds)";

        // 2. Analyze API Call
        const analyzeResponse = await fetch(`${API_BASE_URL}/analyze-resume/${resumeId}`, {
            method: 'POST'
        });

        const analyzeData = await analyzeResponse.json();

        if (!analyzeResponse.ok) {
            throw new Error(analyzeData.detail || "Analysis failed");
        }

        // 3. Display Results
        msg.style.color = "green";
        msg.innerText = "Analysis Complete!";

        const results = analyzeData.analysis_results;
        document.getElementById('res-summary').innerText = results.ai_summary || "N/A";
        document.getElementById('res-tech').innerText = results.technical_skills || "N/A";
        document.getElementById('res-soft').innerText = results.soft_skills || "N/A";
        document.getElementById('res-edu').innerText = results.education_details || "N/A";
        document.getElementById('res-exp').innerText = results.experience_details || "N/A";

        // Show the results section and action buttons
        document.getElementById('results-area').style.display = 'block';
        document.getElementById('action-buttons').style.display = 'flex';

    } catch (error) {
        msg.style.color = "red";
        msg.innerText = error.message || "An error occurred during the process.";
    } finally {
        uploadBtn.disabled = false;
    }
}


async function addJob() {
    const title = document.getElementById('job-title').value;
    const desc = document.getElementById('job-desc').value;
    const skills = document.getElementById('job-skills').value;
    const level = document.getElementById('job-level').value;
    const msg = document.getElementById('job-msg');

    try {
        const response = await fetch(`${API_BASE_URL}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                description: desc,
                required_skills: skills,
                experience_level: level
            })
        });

        if (response.ok) {
            msg.style.color = "green";
            msg.innerText = "Job added successfully!";

            document.getElementById('job-title').value = '';
            document.getElementById('job-desc').value = '';
            document.getElementById('job-skills').value = '';
            document.getElementById('job-level').value = '';
        } else {
            msg.style.color = "red";
            msg.innerText = "Failed to add job.";
        }
    } catch (error) {
        msg.innerText = "Server connection error.";
    }
}


async function getCareerAdvice() {
    const resumeId = localStorage.getItem('resume_id');
    const resultsArea = document.getElementById('extra-results-area');

    resultsArea.innerHTML = "<p style='color: blue;'>Generating career advice... Please wait.</p>";

    try {
        const response = await fetch(`${API_BASE_URL}/career-advice/${resumeId}`);
        const data = await response.json();

        if (response.ok) {
            const advice = data.advice;
            resultsArea.innerHTML = `
                <div class="result-card" style="border-left-color: #17a2b8;">
                    <h4>Career Advice & Insights</h4>
                    <p><strong>Areas for Improvement:</strong> ${advice.weaknesses || "N/A"}</p>
                    <p><strong>Missing Skills to Learn:</strong> ${advice.missing_skills ? (Array.isArray(advice.missing_skills) ? advice.missing_skills.join(', ') : advice.missing_skills) : "N/A"}</p>
                    <p><strong>Recommended Certifications:</strong> ${advice.recommended_certifications ? (Array.isArray(advice.recommended_certifications) ? advice.recommended_certifications.join(', ') : advice.recommended_certifications) : "N/A"}</p>
                </div>
            `;
        }
    } catch (error) {
        resultsArea.innerHTML = "<p style='color: red;'>Failed to get advice.</p>";
    }
}


async function matchJobs() {
    const resumeId = localStorage.getItem('resume_id');
    const resultsArea = document.getElementById('extra-results-area');

    resultsArea.innerHTML = "<p style='color: blue;'>Searching for the best matching jobs... Please wait.</p>";

    try {
        const response = await fetch(`${API_BASE_URL}/match-jobs/${resumeId}`);
        const data = await response.json();

        if (response.ok) {
            if (data.message) {
                resultsArea.innerHTML = `<p style='color: orange;'>${data.message}</p>`;
                return;
            }

            const matches = data.ai_recommendations.matches;
            let htmlContent = `<h3>Top Matched Jobs</h3>`;

            if (Array.isArray(matches)) {
                matches.forEach(match => {
                    htmlContent += `
                        <div class="result-card" style="border-left-color: #28a745;">
                            <h4>${match.job_title} (Match: ${match.matching_score})</h4>
                            <p><strong>Why:</strong> ${match.explanation}</p>
                        </div>
                    `;
                });
            } else {
                htmlContent += `<p>No matches found in the expected format.</p>`;
            }
            resultsArea.innerHTML = htmlContent;
        }
    } catch (error) {
        resultsArea.innerHTML = "<p style='color: red;'>Failed to match jobs.</p>";
    }
}