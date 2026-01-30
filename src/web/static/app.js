/* SJ Home Agent - Minimal JavaScript */
document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    var flash = document.querySelector('.flash');
    if (flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            flash.style.transition = 'opacity 0.5s';
            setTimeout(function() { flash.remove(); }, 500);
        }, 5000);
    }
});
