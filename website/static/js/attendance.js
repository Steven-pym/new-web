document.addEventListener("DOMContentLoaded", function () {
    // Ensure Flask data is safely converted to JSON
    const dailyData = JSON.parse('{{ daily_data | tojson | safe }}');
    const weeklyData = JSON.parse('{{ weekly_data | tojson | safe }}');
    const monthlyData = JSON.parse('{{ monthly_data | tojson | safe }}');

    console.log("Daily Data:", dailyData); // Debugging: Check daily data
    console.log("Weekly Data:", weeklyData); // Debugging: Check weekly data
    console.log("Monthly Data:", monthlyData); // Debugging: Check monthly data

    const ctx = document.getElementById('attendanceChart').getContext('2d');

    // Initialize the chart with daily data
    let attendanceChart = new Chart(ctx, {
        type: 'line', // You can change this to bar or other types
        data: {
            labels: dailyData.labels,
            datasets: [{
                label: 'Attendance Data',
                data: dailyData.data,
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // Allow chart to resize
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Attendance Count'
                    }
                }
            }
        }
    });

    // Function to update chart based on dropdown selection
    function updateChart() {
        const range = document.getElementById('attendanceRange').value;
        let newData;

        if (range === 'daily') {
            newData = dailyData;
        } else if (range === 'weekly') {
            newData = weeklyData;
        } else {
            newData = monthlyData;
        }

        // Show loading spinner
        document.getElementById('loadingSpinner').classList.remove('d-none');

        // Update chart data after a slight delay to simulate loading
        setTimeout(() => {
            attendanceChart.data.labels = newData.labels;
            attendanceChart.data.datasets[0].data = newData.data;
            attendanceChart.update();

            // Hide loading spinner
            document.getElementById('loadingSpinner').classList.add('d-none');
        }, 500); // Adjust delay as needed
    }
});