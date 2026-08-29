document.addEventListener("DOMContentLoaded", () => {

    const loading = document.querySelector(".loading-screen");
    const result = document.querySelector(".result-overlay");

    window.showLoading = function(message = "Generating Questions...") {

        if (!loading) return;

        loading.classList.add("active");

        const txt = loading.querySelector(".loading-text");

        if (txt) txt.innerText = message;
    }

    window.hideLoading = function() {

        if (!loading) return;

        loading.classList.remove("active");
    }

    window.showResult = function() {

        if (!result) return;

        result.classList.add("show");
    }

    window.hideResult = function() {

        if (!result) return;

        result.classList.remove("show");
    }

});