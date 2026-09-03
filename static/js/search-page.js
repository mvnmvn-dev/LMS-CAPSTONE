document.addEventListener('DOMContentLoaded', () => {
    const filterShell = document.getElementById('search-filter-shell');
    const filterRoot = document.getElementById('search-filter-root');
    const filterToggle = document.getElementById('search-filter-toggle');
    const filterToggleMeta = document.getElementById('search-filter-toggle-meta');
    const filterToolbarTags = document.getElementById('search-filter-toolbar-tags');
    const resultsRoot = document.getElementById('search-results-root');
    const modalsRoot = document.getElementById('search-reserve-modals');
    const resultsApi = window.LMS_URLS?.searchResults;
    const searchIndex = window.LMS_URLS?.searchIndex || '/search/';
    const FILTER_STORAGE_KEY = 'lms-search-filters-open';

    if (!filterRoot || !resultsRoot || !resultsApi) return;

    let activeController = null;

    function isFilterOpen() {
        return !filterRoot.classList.contains('is-collapsed');
    }

    function setFilterOpen(open, persist = true) {
        filterRoot.classList.toggle('is-collapsed', !open);
        if (filterToggle) {
            filterToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            const chevron = filterToggle.querySelector('.search-filter-chevron');
            if (chevron) chevron.classList.toggle('is-open', open);
        }
        if (filterToggleMeta) {
            filterToggleMeta.textContent = open ? 'Hide' : 'Show';
        }
        if (persist) {
            localStorage.setItem(FILTER_STORAGE_KEY, open ? '1' : '0');
        }
        syncFilterToolbar();
    }

    function syncFilterToolbar() {
        if (!filterToolbarTags) return;
        const active = filterRoot.querySelector('.search-active-filters');
        if (isFilterOpen() || !active) {
            filterToolbarTags.hidden = true;
            filterToolbarTags.innerHTML = '';
            return;
        }
        filterToolbarTags.hidden = false;
        filterToolbarTags.innerHTML = active.innerHTML;
    }

    if (filterToggle) {
        const saved = localStorage.getItem(FILTER_STORAGE_KEY);
        setFilterOpen(saved === '1', false);
        filterToggle.addEventListener('click', () => setFilterOpen(!isFilterOpen()));
    }

    function paramsFromUrl(url) {
        const parsed = new URL(url, window.location.origin);
        return parsed.searchParams;
    }

    function paramsFromForm(form) {
        const params = new URLSearchParams();
        new FormData(form).forEach((value, key) => {
            if (value !== '' && value != null) params.set(key, value);
        });
        return params;
    }

    function buildResultsUrl(params) {
        const query = params.toString();
        return query ? `${resultsApi}?${query}` : resultsApi;
    }

    function buildPageUrl(params) {
        const query = params.toString();
        return query ? `${searchIndex}?${query}` : searchIndex;
    }

    function setLoading(isLoading) {
        resultsRoot.classList.toggle('is-loading', isLoading);
    }

    function updateResultsCount(total) {
        const count = document.getElementById('search-results-count');
        if (!count) return;
        count.innerHTML = `<i class="fas fa-book"></i> ${total} result${total === 1 ? '' : 's'}`;
    }

    function updateClearButton(hasFilters) {
        const clearBtn = document.getElementById('search-clear-all-btn');
        if (!clearBtn) return;
        clearBtn.hidden = !hasFilters;
    }

    async function loadSearch(params, { pushState = true } = {}) {
        if (activeController) activeController.abort();
        activeController = new AbortController();
        setLoading(true);

        try {
            const response = await fetch(buildResultsUrl(params), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: activeController.signal,
            });
            if (!response.ok) throw new Error('Search request failed');

            const data = await response.json();
            filterRoot.innerHTML = data.filters_html;
            resultsRoot.innerHTML = data.results_html;
            if (modalsRoot) modalsRoot.innerHTML = data.modals_html || '';

            updateResultsCount(data.total);
            updateClearButton(data.has_filters);
            syncFilterToolbar();

            if (window.bindSearchInteractions) {
                window.bindSearchInteractions(resultsRoot);
                if (modalsRoot) window.bindSearchInteractions(modalsRoot);
            }

            if (pushState) {
                const pageUrl = buildPageUrl(params);
                if (pageUrl !== window.location.pathname + window.location.search) {
                    history.pushState({ searchParams: params.toString() }, '', pageUrl);
                }
            }

            resultsRoot.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } catch (error) {
            if (error.name !== 'AbortError') {
                window.location.href = buildPageUrl(params);
            }
        } finally {
            setLoading(false);
        }
    }

    function navigateFromLink(link) {
        const params = paramsFromUrl(link.href);
        loadSearch(params);
    }

    document.addEventListener('click', (event) => {
        const ajaxLink = event.target.closest('[data-search-ajax-link]');
        if (ajaxLink) {
            event.preventDefault();
            navigateFromLink(ajaxLink);
            return;
        }

        const pageLink = event.target.closest('#search-results-root .table-pagination a');
        if (pageLink) {
            event.preventDefault();
            navigateFromLink(pageLink);
        }
    });

    document.addEventListener('submit', (event) => {
        const form = event.target.closest('[data-search-ajax-form]');
        if (!form) return;
        event.preventDefault();

        const params = paramsFromForm(form);
        params.delete('page');

        if (form.closest('#search-modal')) {
            if (window.closeModal) window.closeModal('search-modal');
        }

        if (!isFilterOpen()) {
            setFilterOpen(true);
        }

        loadSearch(params);
    });

    window.addEventListener('popstate', (event) => {
        const params = event.state?.searchParams
            ? new URLSearchParams(event.state.searchParams)
            : paramsFromUrl(window.location.href);
        loadSearch(params, { pushState: false });
    });

    if (!history.state?.searchParams) {
        history.replaceState(
            { searchParams: window.location.search.replace(/^\?/, '') },
            '',
            window.location.href
        );
    }

    syncFilterToolbar();
});
