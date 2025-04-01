window.addEventListener("load", function () {
    // Hide preloader after a short delay
    setTimeout(() => {
      document.getElementById("preloader").style.display = "none";
    }, 500);
  });

  // Scroll effect for navbar
  window.addEventListener('scroll', function() {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });