const imprimir = document.getElementById('imprimir');
imprimir.hidden = false;
imprimir.disabled = false;
imprimir.addEventListener('click', () => window.print());
