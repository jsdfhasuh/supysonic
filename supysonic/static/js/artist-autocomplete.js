(function() {
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function highlightArtistMatch(artistName, query) {
    const normalizedName = artistName.toLowerCase();
    const normalizedQuery = query.toLowerCase();
    const matchIndex = normalizedName.indexOf(normalizedQuery);
    if (matchIndex < 0 || !normalizedQuery) {
      return escapeHtml(artistName);
    }

    const before = escapeHtml(artistName.slice(0, matchIndex));
    const match = escapeHtml(artistName.slice(matchIndex, matchIndex + query.length));
    const after = escapeHtml(artistName.slice(matchIndex + query.length));
    return `${before}<span class="artist-autocomplete-match">${match}</span>${after}`;
  }

  function showArtistSuggestionMessage(autocompleteState, message, className) {
    autocompleteState.suggestionsNode.innerHTML = '';
    autocompleteState.selectedIndex = -1;
    const messageNode = document.createElement('div');
    messageNode.className = className;
    messageNode.textContent = message;
    autocompleteState.suggestionsNode.appendChild(messageNode);
    autocompleteState.suggestionsNode.classList.remove('d-none');
  }

  function clearArtistSuggestions(autocompleteState) {
    if (!autocompleteState || !autocompleteState.suggestionsNode) {
      return;
    }
    autocompleteState.suggestionsNode.innerHTML = '';
    autocompleteState.suggestionsNode.classList.add('d-none');
    autocompleteState.selectedIndex = -1;
  }

  function chooseArtistSuggestion(autocompleteState, artistName) {
    if (!autocompleteState || !autocompleteState.inputNode) {
      return;
    }
    autocompleteState.inputNode.value = artistName;
    clearArtistSuggestions(autocompleteState);
  }

  function chooseSelectedArtistSuggestion(autocompleteState) {
    if (!autocompleteState || autocompleteState.selectedIndex < 0) {
      return;
    }
    const selectedNode = autocompleteState.suggestionsNode.children[autocompleteState.selectedIndex];
    if (selectedNode) {
      chooseArtistSuggestion(autocompleteState, selectedNode.textContent);
    }
  }

  function moveArtistSuggestionSelection(autocompleteState, direction) {
    if (!autocompleteState || !autocompleteState.suggestionsNode.children.length) {
      return;
    }
    const suggestionNodes = Array.from(autocompleteState.suggestionsNode.children);
    autocompleteState.selectedIndex = (autocompleteState.selectedIndex + direction + suggestionNodes.length) % suggestionNodes.length;
    suggestionNodes.forEach((node, index) => {
      node.classList.toggle('active', index === autocompleteState.selectedIndex);
    });
  }

  function renderArtistSuggestions(autocompleteState, artists, query) {
    if (!autocompleteState || !autocompleteState.suggestionsNode) {
      return;
    }
    autocompleteState.suggestionsNode.innerHTML = '';
    autocompleteState.selectedIndex = -1;

    const artistNames = artists || [];
    if (!artistNames.length) {
      showArtistSuggestionMessage(autocompleteState, 'No matching artists found', 'list-group-item artist-autocomplete-empty');
      return;
    }

    artistNames.forEach((artistName) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'list-group-item list-group-item-action';
      button.innerHTML = highlightArtistMatch(artistName, query || '');
      button.addEventListener('click', () => chooseArtistSuggestion(autocompleteState, artistName));
      autocompleteState.suggestionsNode.appendChild(button);
    });
    autocompleteState.suggestionsNode.classList.remove('d-none');
  }

  async function requestArtistSuggestions(autocompleteState, query) {
    const response = await fetch(`${autocompleteState.suggestionsUrl}?q=${encodeURIComponent(query.trim())}`);
    const payload = await response.json();
    if (!response.ok || payload.status === 'error') {
      throw new Error(payload.message || 'Failed to load artist suggestions');
    }
    renderArtistSuggestions(autocompleteState, payload.artists || [], query);
  }

  function setupArtistAutocomplete(inputNode, suggestionsNode, options) {
    if (!inputNode || !suggestionsNode) {
      return null;
    }

    const autocompleteState = {
      inputNode,
      suggestionsNode,
      suggestionsUrl: options.suggestionsUrl,
      selectedIndex: -1,
      debounceTimer: null,
      minLength: options.minLength || 2,
      debounceMs: options.debounceMs || 150,
    };

    inputNode.addEventListener('focus', function() {
      if (typeof options.onFocus === 'function') {
        options.onFocus(autocompleteState);
      }
    });

    inputNode.addEventListener('input', function() {
      if (typeof options.onFocus === 'function') {
        options.onFocus(autocompleteState);
      }
      window.clearTimeout(autocompleteState.debounceTimer);
      autocompleteState.debounceTimer = window.setTimeout(async function() {
        if (!inputNode.value || inputNode.value.trim().length < autocompleteState.minLength) {
          clearArtistSuggestions(autocompleteState);
          return;
        }
        showArtistSuggestionMessage(autocompleteState, 'Searching artists...', 'list-group-item artist-autocomplete-loading');
        try {
          await requestArtistSuggestions(autocompleteState, inputNode.value);
        } catch (error) {
          clearArtistSuggestions(autocompleteState);
        }
      }, autocompleteState.debounceMs);
    });

    inputNode.addEventListener('keydown', function(event) {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        moveArtistSuggestionSelection(autocompleteState, 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        moveArtistSuggestionSelection(autocompleteState, -1);
      } else if (event.key === 'Enter') {
        if (autocompleteState.selectedIndex >= 0) {
          event.preventDefault();
          chooseSelectedArtistSuggestion(autocompleteState);
        }
      } else if (event.key === 'Escape') {
        clearArtistSuggestions(autocompleteState);
      }
    });

    inputNode.addEventListener('blur', function() {
      window.setTimeout(() => clearArtistSuggestions(autocompleteState), 150);
    });

    autocompleteState.clear = function() {
      clearArtistSuggestions(autocompleteState);
    };
    return autocompleteState;
  }

  window.setupArtistAutocomplete = setupArtistAutocomplete;
})();
