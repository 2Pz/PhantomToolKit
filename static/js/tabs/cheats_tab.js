function renderCheats() {
      const container = document.getElementById('cheats-container');
      if (!container) return;

      container.innerHTML = cheatList.map(cheat => {
        const isActive = cheatsState[cheat.key];
        return `
          <div
            onclick="toggleCheat('${cheat.key}')"
            class="p-5 border flex items-center justify-between transition-all duration-300 group relative overflow-hidden cursor-pointer ${
              isActive
                ? 'bg-[#bfa571]/10 border-[#bfa571] shadow-[0_0_15px_rgba(191,165,113,0.1)]'
                : 'bg-black/40 border-white/5 hover:border-white/20 hover:bg-white/5'
            }"
          >
            <div class="flex flex-col pr-4">
              <h4 class="fantasy-font uppercase tracking-wider text-lg leading-tight ${isActive ? 'text-[#bfa571]' : 'text-gray-200'}">
                ${cheat.label}
              </h4>
              <p class="text-[11px] text-gray-500 mt-1.5 font-light tracking-wide">${cheat.desc}</p>
            </div>

            <div class="w-10 h-5 rounded-full p-1 transition-colors duration-300 relative shrink-0 border ${isActive ? 'bg-[#bfa571] border-[#bfa571]' : 'bg-black/60 border-white/20 group-hover:border-white/40'}">
              <div class="w-3 h-3 bg-white rounded-full transition-transform duration-300 ${isActive ? 'translate-x-5' : 'translate-x-0'}"></div>
            </div>
          </div>
        `;
      }).join('');
    }

function toggleCheat(key) {
      const newState = !cheatsState[key];
      // Optimistic UI update
      cheatsState[key] = newState;
      renderCheats();

      fetch('/api/cheats/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cheat: key, enabled: newState })
      })
      .then(res => res.json())
      .then(data => {
        if (!data.success) {
          // Revert on failure
          cheatsState[key] = !newState;
          renderCheats();
          alert('Failed to toggle cheat: ' + (data.message || 'Unknown error'));
        }
      })
      .catch(err => {
        console.error('Error toggling cheat:', err);
        cheatsState[key] = !newState;
        renderCheats();
      });
    }