(function () {
    function normalize(value) {
        return (value || '').trim().toLowerCase();
    }

    function filterCatalog(input) {
        var query = normalize(input.value);
        var tree = document.getElementById('discipline-catalog');
        if (!tree) {
            return;
        }

        tree.querySelectorAll('.catalog-discipline').forEach(function (discipline) {
            var title = discipline.querySelector('.catalog-discipline__title');
            var text = normalize(title && title.textContent);
            var match = !query || text.indexOf(query) !== -1;
            discipline.classList.toggle('is-filter-hidden', !match);
        });

        tree.querySelectorAll('.catalog-dept').forEach(function (dept) {
            var visible = dept.querySelectorAll('.catalog-discipline:not(.is-filter-hidden)').length > 0;
            dept.classList.toggle('is-filter-hidden', !visible && query.length > 0);
            if (visible && query) {
                dept.setAttribute('open', 'open');
            }
        });
    }

    document.addEventListener('input', function (event) {
        if (event.target && event.target.id === 'discipline-search') {
            filterCatalog(event.target);
        }
    });
})();
