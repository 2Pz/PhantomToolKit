function inspectPlayer(steamId, playerIndex, name, isLocal) {
      inspectingSteamId = isLocal ? null : (steamId || null);
      inspectingPlayerIndex = isLocal ? null : playerIndex;
      inspectingCachedBuild = false;
      inspectingName = name || '';
      buildDirty = false;
      pendingItem = null;
      selectedSlot = null;
      ashResults = [];
      ashQuery = '';
      openBuildTabShell();
      updateBuild(true);
    }

function inspectRecentPlayer(index) {
      const player = recentPlayers[index];
      if (!player) return;
      inspectingSteamId = player.steam_id || null;
      inspectingPlayerIndex = null;
      inspectingCachedBuild = true;
      inspectingName = player.name || 'Recent Player';
      pendingItem = null;
      selectedSlot = null;
      ashResults = [];
      ashQuery = '';
      openBuildTabShell();
      document.getElementById('build-connection').innerText = 'Loading Recent';
      if (player.build_snapshot) {
        openRecentSnapshot(player.name || 'Recent Player', player.build_snapshot);
        return;
      }
      if (player.steam_id) {
        fetch('/api/build/recent/' + encodeURIComponent(player.steam_id))
          .then(res => res.json())
          .then(data => {
            if (data.loaded) {
              openRecentSnapshot(player.name || 'Recent Player', data);
              return;
            }
            fetch('/api/build?steam_id=' + encodeURIComponent(player.steam_id))
              .then(res => res.json())
              .then(live => {
                if (live.loaded) openRecentSnapshot(player.name || 'Recent Player', live);
                else openMissingRecentBuild(player.name || 'Recent Player', data.message || live.message || 'No build data available for this recent player.');
              })
              .catch(() => openMissingRecentBuild(player.name || 'Recent Player', data.message || 'No build data available for this recent player.'));
          })
          .catch(() => openMissingRecentBuild(player.name || 'Recent Player', 'Failed to load recent build.'));
        return;
      }
      openMissingRecentBuild(player.name || 'Recent Player', 'No build data available for this recent player.');
    }

function openRecentSnapshot(name, snapshot) {
      inspectingCachedBuild = true;
      inspectingName = name;
      localBuild = snapshot.build || { slots: {} };
      localStatus = snapshot.status || {};
      localAppearance = snapshot.appearance || null;
      buildDirty = true;
      renderStatusPanel();
      renderEquipmentGrid();
      renderConfigPanel();
    }

function openBuildTabShell() {
      document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
      const buildButton = Array.from(document.querySelectorAll('.sidebar-btn')).find(btn => btn.textContent.trim().toLowerCase() === 'build');
      if (buildButton) buildButton.classList.add('active');
      activeTab = 'build';
      const mainTab = document.getElementById('main-tab'); if(mainTab) mainTab.classList.add('hidden');
      const cheatsTab = document.getElementById('cheats-tab'); if(cheatsTab) cheatsTab.classList.add('hidden');
      const backupTab = document.getElementById('backup-tab'); if(backupTab) backupTab.classList.add('hidden');
      const invTab = document.getElementById('inventory-tab'); if(invTab) invTab.classList.add('hidden');
      const buildTab = document.getElementById('build-tab'); if(buildTab) buildTab.classList.remove('hidden');
    }

function openMissingRecentBuild(name, message) {
      inspectingSteamId = null;
      inspectingPlayerIndex = null;
      inspectingCachedBuild = true;
      inspectingName = name;
      localBuild = { slots: {} };
      localStatus = { name };
      localAppearance = null;
      buildDirty = true;
      openBuildTabShell();
      document.getElementById('build-connection').innerText = 'No Snapshot';
      renderStatusPanel();
      renderEquipmentGrid();
      renderConfigPanel();
      document.getElementById('config-panel').innerHTML = `<div class="text-xs text-gray-400">${escapeHtml(message)}</div>`;
    }

function copyViewedBuild() {
      inspectingSteamId = null;
      inspectingPlayerIndex = null;
      inspectingCachedBuild = false;
      inspectingName = '';
      buildDirty = true;
      renderStatusPanel();
      renderEquipmentGrid();
      renderConfigPanel();
    }

function markBuildEditing() {
      if (isInspectingBuild()) return;
      buildDirty = true;
      const state = document.getElementById('build-edit-state');
      if (state) {
        state.innerText = 'Editing - Sync Paused';
        state.classList.remove('text-gray-500');
        state.classList.add('text-[#bfa571]');
      }
      const connection = document.getElementById('build-connection');
      if (connection) connection.innerText = 'Editing';
    }

function refreshBuildFromGame() {
      buildDirty = false;
      pendingItem = null;
      ashResults = [];
      ashQuery = '';
      updateBuild(true);
    }

function updateBuild(force) {
      if (activeTab !== 'build') return;
      if (buildDirty && !force) return;

      const url = inspectingPlayerIndex !== null && inspectingPlayerIndex !== undefined
        ? '/api/build?player_index=' + encodeURIComponent(inspectingPlayerIndex)
        : (inspectingSteamId ? '/api/build?steam_id=' + encodeURIComponent(inspectingSteamId) : '/api/build');
      fetch(url)
        .then(res => res.json())
        .then(data => {
          if (buildDirty && !force) return;
          if (activeTab !== 'build') return;
          const connection = document.getElementById('build-connection');
          if (!data.loaded) {
            connection.innerText = data.message || window.t('build_waiting', 'Waiting for game load...');
            renderStatusPanel();
            renderEquipmentGrid();
            return;
          }
          connection.innerText = isInspectingBuild() ? 'Inspecting' : 'Game Connected';
          localBuild = data.build || { slots: {} };
          localStatus = data.status || {};
          localAppearance = data.appearance || null;
          buildDirty = false;
          const state = document.getElementById('build-edit-state');
          if (state) {
            state.innerText = isInspectingBuild() ? 'Read Only' : 'Live Sync';
            state.classList.toggle('text-[#bfa571]', isInspectingBuild());
            state.classList.toggle('text-gray-500', !isInspectingBuild());
          }
          renderStatusPanel();
          renderEquipmentGrid();
          renderConfigPanel();
        })
        .catch(() => {
          document.getElementById('build-connection').innerText = 'Server Offline';
        });
    }

function renderStatusPanel() {
      const panel = document.getElementById('build-status-panel');
      const name = localStatus.name || 'Unknown';
      const title = inspectingName || name || '2Pz';
      document.getElementById('build-player-name').innerText = title;
      document.querySelector('#build-tab h2.text-center').innerText = isInspectingBuild() ? `${title}'s Build` : (locales['build_equipment'] || 'Equipment');
      document.getElementById('build-primary-action').innerText = isInspectingBuild() ? (locales['build_copy'] || 'Copy Build') : (locales['build_apply'] || 'Apply Build');
      document.getElementById('copy-build-btn').classList.toggle('hidden', !isInspectingBuild());
      const rows = attributes.map(attr => `
        <label class="flex justify-between items-center pr-2">
          <span class="text-base text-gray-200 Cormorant font-semibold tracking-wide" data-i18n="stat_${attr}">${labelFor(attr)}</span>
          ${renderSpinbox(attr, localStatus[attr], 'text-gray-100', 'w-10')}
        </label>
      `).join('');
      panel.innerHTML = `
        <div class="mb-8">
          <h3 class="text-xs fantasy-font text-[#bfa571] uppercase tracking-[0.25em] mb-4 flex items-center gap-3 border-b border-[#bfa571]/20 pb-2" data-i18n="build_identity">Identity</h3>
          <div class="status-line flex flex-col gap-2">
            <div class="flex justify-between items-center pr-2 mb-1 pb-2 border-b border-white/5">
              <span class="text-xs fantasy-font text-gray-400 uppercase tracking-widest" data-i18n="build_auto_calc">Auto-Calculator</span>
              <button onclick="toggleAutoCalc()" class="px-3 py-1 text-[10px] fantasy-font tracking-widest uppercase transition-all border shadow-sm ${autoCalcLevel ? 'bg-[#bfa571] text-black border-[#bfa571] font-bold hover:brightness-110' : 'bg-transparent text-gray-500 border-white/10 hover:border-white/30 hover:text-gray-300'}" data-i18n="${autoCalcLevel ? 'build_active' : 'build_manual'}">
                ${autoCalcLevel ? 'Active' : 'Manual'}
              </button>
            </div>
            <div class="flex justify-between items-center pr-2">
              <span class="text-xs fantasy-font text-gray-400 uppercase tracking-widest" data-i18n="build_level">Level</span>
              ${renderSpinbox('level', localStatus.level, 'text-gray-100', 'w-14', autoCalcLevel)}
            </div>
            <div class="flex justify-between items-center pr-2">
              <span class="text-xs fantasy-font text-gray-400 uppercase tracking-widest" data-i18n="build_journey">Journey</span>
              ${renderSpinbox('journey', localStatus.journey != null ? localStatus.journey : 1, 'text-gray-100', 'w-10')}
            </div>
          </div>
        </div>

        <div class="mb-8">
          <h3 class="text-xs fantasy-font text-[#bfa571] uppercase tracking-[0.25em] mb-4 flex items-center gap-3 border-b border-[#bfa571]/20 pb-2" data-i18n="build_growth">Growth</h3>
          <div class="status-line flex flex-col gap-2">
            ${statusRow('runes', 'Runes')}
            ${statusRow('scadutree_blessing', 'Scadutree Blessing')}
            ${statusRow('revered_spirit_ash', 'Spirit Blessing')}
          </div>
        </div>

        <div class="flex-1 pb-10">
          <h3 class="text-xs fantasy-font text-[#bfa571] uppercase tracking-[0.25em] mb-4 flex items-center gap-3 border-b border-[#bfa571]/20 pb-2" data-i18n="build_attributes">Attributes</h3>
          <div class="status-line flex flex-col gap-2">${rows}</div>
        </div>
      `;
      if (typeof translateUI === 'function') translateUI();
    }

function statusRow(key, label, golden) {
      return `
        <label class="flex justify-between items-center pr-2">
          <span class="text-xs fantasy-font text-gray-400 uppercase tracking-widest" data-i18n="stat_${key}">${label}</span>
          ${renderSpinbox(key, localStatus[key], golden ? 'text-[#bfa571]' : 'text-gray-100', 'w-16')}
        </label>
      `;
    }

function toggleAutoCalc() {
      autoCalcLevel = !autoCalcLevel;
      if (autoCalcLevel) {
        calculateLevel();
      } else {
        renderStatusPanel();
      }
    }

function calculateLevel() {
      let sum = 0;
      for (const attr of attributes) {
        sum += Number(localStatus[attr]) || 0;
      }
      localStatus.level = Math.max(1, sum - 79);
      markBuildEditing();
      renderStatusPanel();
    }

function renderSpinbox(key, value, extraClass = '', widthClass = 'w-10', readonly = false) {
      if (readonly) {
        return `
          <div class="flex items-center bg-transparent border border-transparent rounded overflow-hidden opacity-80 transition-colors">
            <input id="status-${key}-input" class="bg-transparent text-center font-bold outline-none ${widthClass} inter-font text-base px-1 py-0.5 custom-spinbox-input ${extraClass}" type="number" value="${value != null ? value : ''}" readonly>
          </div>
        `;
      }
      return `
        <div class="flex items-center bg-white/5 border border-transparent hover:border-white/10 rounded overflow-hidden focus-within:border-[#bfa571]/50 transition-colors">
          <button type="button" class="px-2 py-0.5 text-gray-500 hover:text-[#bfa571] hover:bg-white/10 font-bold" onclick="adjustStatus(this, '${key}', -1)" tabindex="-1">-</button>
          <input id="status-${key}-input" class="bg-transparent text-center font-bold outline-none ${widthClass} inter-font text-base px-1 py-0.5 custom-spinbox-input ${extraClass}" type="number" min="0" value="${value != null ? value : ''}" oninput="setStatus('${key}', this.value)">
          <button type="button" class="px-2 py-0.5 text-gray-500 hover:text-[#bfa571] hover:bg-white/10 font-bold" onclick="adjustStatus(this, '${key}', 1)" tabindex="-1">+</button>
        </div>
      `;
    }

function getStatLimits(key) {
      if (attributes.includes(key)) return { min: 1, max: 99 };
      if (key === 'level') return { min: 1, max: 713 };
      if (key === 'journey') return { min: 1, max: 99 };
      if (key === 'scadutree_blessing') return { min: 0, max: 20 };
      if (key === 'revered_spirit_ash') return { min: 0, max: 10 };
      if (key === 'runes') return { min: 0, max: 999999999 };
      return { min: 0, max: 999999999 };
    }

function adjustStatus(btn, key, delta) {
      const input = btn.parentElement.querySelector('input');
      const limits = getStatLimits(key);
      let current = input.value === '' ? limits.min : Number(input.value);
      let newVal = current + delta;
      newVal = Math.max(limits.min, Math.min(limits.max, newVal));
      input.value = newVal;
      setStatus(key, newVal);
    }

function setStatus(key, value) {
      const limits = getStatLimits(key);
      let val = value === '' ? '' : Number(value);
      
      if (val !== '' && val > limits.max) val = limits.max;
      if (val !== '' && val < limits.min) val = limits.min;
      
      const input = document.getElementById(`status-${key}-input`);
      if (input && input.value !== String(val)) {
        input.value = val;
      }
      
      localStatus[key] = val === '' ? limits.min : val;

      if (autoCalcLevel && attributes.includes(key)) {
        let sum = 0;
        for (const attr of attributes) {
          sum += Number(localStatus[attr]) || limits.min;
        }
        localStatus.level = Math.max(1, sum - 79);
        const levelInput = document.getElementById('status-level-input');
        if (levelInput) levelInput.value = localStatus.level;
      }
      markBuildEditing();
    }

function renderEquipmentGrid() {
      const grid = document.getElementById('equipment-grid');
      grid.innerHTML = `
        <div class="equipment-board flex flex-col gap-0.5 p-4 rounded-md">
          <div class="flex gap-1">
            <div class="flex gap-1">
              ${[1, 2, 3].map(i => renderSlot(`weapon_r_${i}`, `R${i}`)).join('')}
            </div>
            <div class="w-12"></div>
            <div class="flex gap-1">
              ${[1, 2].map(i => renderSlot(`ammo_1_${i}`, `A${i}`)).join('')}
            </div>
          </div>
          <div class="flex gap-1 mt-1">
            <div class="flex gap-1">
              ${[1, 2, 3].map(i => renderSlot(`weapon_l_${i}`, `L${i}`)).join('')}
            </div>
            <div class="w-12"></div>
            <div class="flex gap-1">
              ${[1, 2].map(i => renderSlot(`ammo_2_${i}`, `B${i}`)).join('')}
            </div>
          </div>
          <div class="flex gap-1 mt-6">
            ${renderSlot('head', 'Head')}
            ${renderSlot('chest', 'Chest')}
            ${renderSlot('hands', 'Hands')}
            ${renderSlot('legs', 'Legs')}
          </div>
          <div class="flex gap-12 mt-2">
            <div class="flex gap-1">
              ${[1, 2, 3, 4].map(i => renderSlot(`talisman_${i}`, `T${i}`)).join('')}
            </div>
            <div class="flex items-start -mt-12">
              <div class="relative group">
                <div class="absolute inset-[-4px] rounded-full border border-[#bfa571]/40 pointer-events-none"></div>
                <div class="absolute inset-[-8px] rounded-full border border-[#bfa571]/10 pointer-events-none"></div>
                <div class="rounded-full bg-black/60 overflow-hidden border border-white/5 shadow-xl">
                  ${renderSlot('great_rune', 'Rune', 'w-24 h-24 rounded-full')}
                </div>
              </div>
            </div>
          </div>
          <div class="flex gap-1 mt-6">
            ${[1, 2, 3, 4, 5].map(i => renderSlot(`quick_1_${i}`, `Q${i}`)).join('')}
          </div>
          <div class="flex gap-1">
            ${[6, 7, 8, 9, 10].map(i => renderSlot(`quick_2_${i}`, `Q${i}`)).join('')}
          </div>
          <div class="mt-4 flex flex-col items-center">
            <div class="flex gap-2 items-center mb-1">
              <div class="h-px w-4 bg-white/10"></div>
              <h4 class="text-[9px] fantasy-font text-gray-400 uppercase tracking-[0.2em]">Wondrous Physick</h4>
              <div class="h-px w-4 bg-white/10"></div>
            </div>
            <div class="flex gap-2 justify-center">
              ${renderSlot('physick_tear_1', 'P1', 'w-10 h-10')}
              ${renderSlot('physick_tear_2', 'P2', 'w-10 h-10')}
            </div>
          </div>
          <div class="mt-4 flex flex-col items-center">
            <div class="flex gap-2 items-center mb-1">
              <div class="h-px w-4 bg-white/10"></div>
              <h4 class="text-[9px] fantasy-font text-gray-400 uppercase tracking-[0.2em]">Spells / Memory Slots</h4>
              <div class="h-px w-4 bg-white/10"></div>
            </div>
            <div class="flex flex-col gap-0.5">
              <div class="flex gap-0.5">${[1, 2, 3, 4, 5, 6, 7].map(i => renderSlot(`spell_${i}`, `S${i}`, 'w-10 h-10')).join('')}</div>
              <div class="flex gap-0.5">${[8, 9, 10, 11, 12, 13, 14].map(i => renderSlot(`spell_${i}`, `S${i}`, 'w-10 h-10')).join('')}</div>
            </div>
          </div>
        </div>
      `;
    }

function renderSlot(slot, label, sizeClass) {
      const item = localBuild.slots ? localBuild.slots[slot] : undefined;
      const selected = selectedSlot === slot ? 'selected' : '';
      const size = sizeClass || 'w-16 h-16 md:w-20 md:h-20';
      const icon = item && item.icon_id ? `<img src="/api/icons/${item.icon_id}" alt="${escapeAttr(item.name || '')}" class="w-[85%] h-[85%] object-contain brightness-90 contrast-110 border border-white/5 z-10">` : '';
      const fallback = icon ? '' : `<div class="absolute inset-0 flex items-center justify-center pointer-events-none select-none text-[#555]"><span class="text-[9px] uppercase tracking-widest">${label}</span></div>`;
      const count = item && item.count && item.count > 1 ? `<span class="absolute bottom-1 right-2 text-xs font-bold text-gray-300 z-20 font-mono">${item.count}</span>` : '';
      const upgrade = item && item.upgrade && item.upgrade > 0 ? `<span class="absolute bottom-1 right-1 text-xs font-bold text-cyan-200 z-20 font-mono bg-black/40 px-1 rounded-sm">+${item.upgrade}</span>` : '';
      return `
        <button title="${escapeAttr((item && item.name) || label)}" class="relative soulslike-slot slot-corner cursor-pointer flex items-center justify-center transition-all duration-200 ${size} ${selected}" onmouseenter="hoveredSlot='${slot}'" onmouseleave="hoveredSlot=null" onclick="selectSlot('${slot}')" oncontextmenu="event.preventDefault(); clearSlot('${slot}');">
          ${fallback}
          ${icon}
          ${count}
          ${upgrade}
        </button>
      `;
    }

function slotSubText(item) {
      const parts = [];
      if (item.category) parts.push(item.category);
      if (item.upgrade) parts.push('+' + item.upgrade);
      if (item.count) parts.push('x' + item.count);
      if (item.ash_of_war && item.ash_of_war !== -1) parts.push('AoW ' + item.ash_of_war);
      return parts.join(' · ');
    }

function selectSlot(slot) {
      selectedSlot = slot;
      pendingItem = null;
      selectedCategory = '';
      markBuildEditing();
      document.getElementById('selected-slot-label').innerText = slotLabel(slot);
      document.getElementById('item-search').value = '';
      
      const item = localBuild.slots[slot];
      if (item && item.category) {
        selectedCategory = item.category;
      }
      
      searchResults = [];
      document.getElementById('search-results').innerHTML = '<div class="col-span-5 text-xs text-gray-500">Searching...</div>';
      
      // Load categories and run search when done to avoid race conditions
      fetch('/api/items/categories?slot=' + encodeURIComponent(slot))
        .then(res => res.json())
        .then(data => {
          const select = document.getElementById('category-filter');
          const cats = data.categories || [];
          select.innerHTML = '<option value="">ALL</option>' + cats.map(cat => `<option value="${escapeAttr(cat)}">${escapeHtml(cat)}</option>`).join('');
          select.value = selectedCategory;
          runItemSearch();
        });
        
      renderEquipmentGrid();
      renderConfigPanel();
      
      if (item) {
        customizeCurrentItem();
      }
    }

function loadCategories(slot) {
      // Replaced by inline logic in selectSlot
    }

function queueSearch() {
      markBuildEditing();
      clearTimeout(searchTimer);
      searchTimer = setTimeout(runItemSearch, 300);
    }

function runItemSearch() {
      if (!selectedSlot) return;
      selectedCategory = document.getElementById('category-filter').value;
      const q = document.getElementById('item-search').value;
      const limit = selectedCategory ? 500 : 50;
      const params = new URLSearchParams({ slot: selectedSlot, q, equip_only: '1', limit: String(limit) });
      if (selectedCategory) params.set('category', selectedCategory);
      fetch('/api/items/search?' + params.toString())
        .then(res => res.json())
        .then(data => {
          searchResults = filterSlotResults(selectedSlot, data.items || []);
          document.getElementById('search-results').innerHTML = searchResults.map(renderSearchItem).join('') || '<div class="col-span-5 text-xs text-gray-500">No items found.</div>';
          
          const equipped = localBuild.slots[selectedSlot];
          if (equipped && !q) {
             const index = searchResults.findIndex(i => i.id === equipped.id || i.name === equipped.name || i.id === equipped.base_id);
             if (index >= 0) {
                 setTimeout(() => {
                     const btn = document.getElementById('search-results').children[index];
                     if (btn) {
                         btn.scrollIntoView({ behavior: 'auto', block: 'center' });
                         btn.classList.add('border', 'border-[#bfa571]', 'shadow-[0_0_10px_rgba(191,165,113,0.5)]');
                     }
                 }, 50);
             }
          }
        });
    }

function filterSlotResults(slot, items) {
      if (!slot) return items;
      if (slot.startsWith('physick_tear_')) return items.filter(item => item.category === 'Wondrous Physick Tear');
      if (slot === 'ammo_1_1' || slot === 'ammo_1_2') return items.filter(item => item.category === 'arrow');
      if (slot === 'ammo_2_1' || slot === 'ammo_2_2') return items.filter(item => item.category === 'bolt');
      if (slot.startsWith('talisman_')) return items.filter(item => item.category === 'Accessory');
      return items;
    }

function renderSearchItem(item, index) {
      return `
        <button title="${escapeAttr(item.name)}" class="aspect-square soulslike-slot flex items-center justify-center transition-all relative cursor-pointer hover:selected-highlight" onclick="selectPendingItemByIndex(${index})">
          ${item.icon_id ? `<img src="/api/icons/${item.icon_id}" alt="${escapeAttr(item.name)}" class="w-[85%] h-[85%] object-contain p-1 transition-all">` : `<span class="text-[9px] text-center text-gray-500 p-1">${escapeHtml(item.name)}</span>`}
        </button>
      `;
    }

function selectPendingItemByIndex(index) {
      const item = searchResults[index];
      if (item) selectPendingItem(item);
    }

function selectPendingItem(item) {
      if (isInspectingBuild()) return;
      markBuildEditing();
      const finish = (enriched) => {
        pendingItem = { ...(enriched || item), id: item.id, name: item.name, category: item.category || (enriched ? enriched.category : undefined), icon_id: item.icon_id || (enriched ? enriched.icon_id : undefined) };
        if (isAmmoSlot(selectedSlot) && !pendingItem.count) pendingItem.count = 99;
        if (isQuickSlot(selectedSlot) && !pendingItem.is_only_one && pendingItem.count === undefined) pendingItem.count = null;
        ashResults = [];
        ashQuery = '';
        renderConfigPanel();
        if (isWeaponSlot(selectedSlot) && pendingItem.max_upgrade) runAshSearch();
      };
      if (isWeaponSlot(selectedSlot)) {
        fetch('/api/items/enrich/weapon?id=' + encodeURIComponent(item.id))
          .then(res => res.json())
          .then(data => finish(data.item))
          .catch(() => finish(null));
        return;
      }
      if (item.category && item.category.toLowerCase().includes('spirit summon')) {
        fetch('/api/items/enrich/goods?id=' + encodeURIComponent(item.id))
          .then(res => res.json())
          .then(data => finish(data.item))
          .catch(() => finish(null));
        return;
      }
      finish(null);
    }

function renderConfigPanel() {
      const panel = document.getElementById('config-panel');
      const item = pendingItem || (selectedSlot && localBuild.slots ? localBuild.slots[selectedSlot] : null);
      if (!selectedSlot) {
        panel.innerHTML = `
          <div class="flex gap-4">
            <div class="w-20 h-20 soulslike-slot item-glow flex items-center justify-center shrink-0 active"></div>
            <div class="flex-1">
              <h4 class="fantasy-font text-gray-100 uppercase text-base leading-tight">${window.t('build_select_slot_title', 'Select Slot')}</h4>
              <div class="flex justify-between items-center mt-2 border-b border-white/5 pb-1">
                <span class="text-[10px] text-gray-500 uppercase tracking-widest">${window.t('build_status', 'Status')}</span>
                <span class="text-xs text-[#bfa571] font-bold">${window.t('build_ready', 'Ready')}</span>
              </div>
            </div>
          </div>
        `;
        return;
      }
      if (!item) {
        panel.innerHTML = `
          <div class="flex gap-4">
            <div class="w-20 h-20 soulslike-slot item-glow flex items-center justify-center shrink-0 active"></div>
            <div class="flex-1">
              <h4 class="fantasy-font text-gray-100 uppercase text-base leading-tight">${slotLabel(selectedSlot)}</h4>
              <div class="flex justify-between items-center mt-2 border-b border-white/5 pb-1">
                <span class="text-[10px] text-gray-500 uppercase tracking-widest">${window.t('build_id', 'ID')}</span>
                <span class="text-xs text-[#bfa571] font-bold">--</span>
              </div>
              <p class="text-xs text-gray-500 mt-3">${window.t('build_no_equip', 'No item equipped. Use search below to choose one.')}</p>
            </div>
          </div>
        `;
        return;
      }

      const pendingActions = pendingItem ? `
        <div class="grid grid-cols-2 gap-2 mt-3">
          <button class="py-2 bg-[#bfa571] text-black fantasy-font uppercase tracking-widest text-xs font-bold hover:brightness-110" onclick="confirmPendingItem()">${window.t('build_confirm', 'Confirm & Equip')}</button>
          <button class="py-2 bg-white/10 text-gray-300 fantasy-font uppercase tracking-widest text-xs font-bold hover:bg-white/20" onclick="pendingItem=null; renderConfigPanel()">${window.t('build_dismiss', 'Dismiss')}</button>
        </div>
      ` : `
        <button class="w-full mt-4 py-2 bg-white/5 border border-white/10 text-gray-300 fantasy-font uppercase tracking-widest text-xs font-bold hover:bg-white/10 hover:text-[#bfa571] hover:border-[#bfa571]/50 transition-all" onclick="customizeCurrentItem()">${window.t('build_customize', 'Customize Weapon')}</button>
      `;

      panel.innerHTML = `
        <div class="flex flex-col gap-4">
          <div class="flex gap-4">
            <div class="w-20 h-20 soulslike-slot item-glow flex items-center justify-center shrink-0 active">
              ${item.icon_id ? `<img src="/api/icons/${item.icon_id}" class="w-16 h-16 object-contain">` : ''}
            </div>
            <div class="flex-1">
              <h4 class="fantasy-font text-gray-100 uppercase text-base leading-tight">${escapeHtml(item.name || 'Unknown')} ${item.upgrade && !String(item.name || '').includes('+') ? '+' + item.upgrade : ''}</h4>
              <div class="flex justify-between items-center mt-2 border-b border-white/5 pb-1">
                <span class="text-[10px] text-gray-500 uppercase tracking-widest">${window.t('build_id', 'ID')}</span>
                <span class="text-xs text-[#bfa571] font-bold">${item.id || '--'}</span>
              </div>
              <div class="flex justify-between items-center border-b border-white/5 pb-1">
                <span class="text-[10px] text-gray-500 uppercase tracking-widest">${window.t('build_category', 'Category')}</span>
                <span class="text-xs text-[#bfa571] font-bold">${escapeHtml(item.category || '--')}</span>
              </div>
              ${item.ash_of_war && item.ash_of_war !== -1 ? `
              <div class="flex justify-between items-center border-b border-white/5 pb-1">
                <span class="text-[10px] text-gray-500 uppercase tracking-widest">${window.t('build_aow', 'Ash of War')}</span>
                <span class="text-xs text-[#bfa571] font-bold">${escapeHtml(item.ash_of_war_name || item.ash_of_war)}</span>
              </div>
              ` : ''}
            </div>
          </div>
          ${renderWeaponConfig(item)}
          ${renderSpiritConfig(item)}
          ${renderQuantityConfig(item)}
          ${pendingActions}
        </div>
      `;
    }

function customizeCurrentItem() {
      const item = selectedSlot && localBuild.slots ? localBuild.slots[selectedSlot] : null;
      if (item) {
        if (isWeaponSlot(selectedSlot)) {
          fetch('/api/items/enrich/weapon?id=' + encodeURIComponent(item.id))
            .then(res => res.json())
            .then(data => {
              pendingItem = { ...(data.item || item), id: item.id, name: item.name, upgrade: item.upgrade || 0, ash_of_war: item.ash_of_war };
              markBuildEditing();
              ashResults = [];
              ashQuery = '';
              renderConfigPanel();
              if (pendingItem.max_upgrade) runAshSearch();
            });
        } else if (item.category && item.category.toLowerCase().includes('spirit summon')) {
          fetch('/api/items/enrich/goods?id=' + encodeURIComponent(item.id))
            .then(res => res.json())
            .then(data => {
              pendingItem = { ...(data.item || item), count: item.count };
              markBuildEditing();
              renderConfigPanel();
            });
        } else {
          pendingItem = { ...item };
          markBuildEditing();
          renderConfigPanel();
        }
      }
    }

function renderWeaponConfig(item) {
      if (!isWeaponSlot(selectedSlot) || !item || !item.max_upgrade) return '';
      const variants = item.variants ? `
        <label class="block text-xs uppercase tracking-wider text-gray-500 mt-3">
          Affinity
          <select class="build-input mt-1" onchange="markBuildEditing(); pendingItem.id=Number(this.value); pendingItem.name=this.options[this.selectedIndex].text; renderConfigPanel()">
            <option value="${item.base_id || item.id}">${escapeHtml(item.base_name || item.name)}</option>
            ${item.variants.map(v => `<option value="${v.id}" ${v.id === item.id ? 'selected' : ''}>${escapeHtml(v.name)}</option>`).join('')}
          </select>
        </label>
      ` : '';
      return `
        ${variants}
        <label class="block text-xs uppercase tracking-wider text-gray-500 mt-3">
          ${window.t('build_upgrade', 'Upgrade +')}${item.upgrade || 0}
          <input class="w-full accent-[#bfa571] mt-2" type="range" min="0" max="${item.max_upgrade}" value="${item.upgrade || 0}" oninput="markBuildEditing(); pendingItem.upgrade=Number(this.value); renderConfigPanel()">
        </label>
        <div class="mt-3">
          <div class="flex items-center justify-between text-xs uppercase tracking-wider text-gray-500 mb-1">
            <span>${window.t('build_aow', 'Ash of War')}</span>
            <button class="text-[#bfa571]" onclick="markBuildEditing(); pendingItem.ash_of_war=-1; delete pendingItem.ash_of_war_name; renderConfigPanel()">${window.t('build_none', 'None')}</button>
          </div>
          <input id="ash-search" class="build-input" placeholder="Search ashes..." value="${escapeAttr(ashQuery)}" oninput="queueAshSearch()">
          <div id="ash-results" class="grid grid-cols-4 gap-2 mt-2 max-h-48 overflow-y-auto custom-scrollbar">${renderAshResults()}</div>
          <div class="text-[10px] text-gray-500 mt-1">${window.t('build_selected', 'Selected:')} ${item.ash_of_war && item.ash_of_war !== -1 ? escapeHtml(item.ash_of_war_name || item.ash_of_war) : 'None'}</div>
        </div>
      `;
    }

function runAshSearch() {
      const input = document.getElementById('ash-search');
      if (!input || !pendingItem) return;
      ashQuery = input.value;
      const seq = ++ashSearchSeq;
      const params = new URLSearchParams({ csv: 'EquipParamGem.csv', q: ashQuery, equip_only: '0', limit: '1000' });
      fetch('/api/items/search?' + params.toString())
        .then(res => res.json())
        .then(data => {
          if (seq !== ashSearchSeq) return;
          ashResults = data.items || [];
          const target = document.getElementById('ash-results');
          if (!target) return;
          target.innerHTML = renderAshResults();
          
          if (pendingItem && pendingItem.ash_of_war && pendingItem.ash_of_war !== -1) {
            setTimeout(() => {
              const selectedBtn = target.querySelector('.selected-ash-btn');
              if (selectedBtn) {
                selectedBtn.scrollIntoView({ behavior: 'auto', block: 'center' });
              }
            }, 50);
          }
        });
    }

function selectAshOfWar(itemId) {
      if (!pendingItem) return;
      markBuildEditing();
      pendingItem.ash_of_war = itemId;
      const ashItem = ashResults.find(i => i.id === itemId);
      if (ashItem) {
        pendingItem.ash_of_war_name = ashItem.name;
      } else {
        delete pendingItem.ash_of_war_name;
      }
      renderConfigPanel();
    }

function renderSpiritConfig(item) {
      if (!item || !item.category || !item.category.toLowerCase().includes('spirit summon') || !item.variants) return '';
      return `
        <label class="block text-xs uppercase tracking-wider text-gray-500 mt-3">
          ${window.t('build_spirit_upg', 'Spirit Upgrade')}
          <select class="build-input mt-1" onchange="markBuildEditing(); pendingItem.id=Number(this.value); pendingItem.name=this.options[this.selectedIndex].text; renderConfigPanel()">
            <option value="${item.base_id || item.id}">${escapeHtml(item.base_name || item.name)}</option>
            ${item.variants.map(v => `<option value="${v.id}" ${v.id === item.id ? 'selected' : ''}>${escapeHtml(v.name)}</option>`).join('')}
          </select>
        </label>
      `;
    }

function renderQuantityConfig(item) {
      if (!item || (!isQuickSlot(selectedSlot) && !isAmmoSlot(selectedSlot)) || item.is_only_one) return '';
      const max = item.max_num || 99;
      const current = item.count != null ? item.count : (isAmmoSlot(selectedSlot) ? 99 : 1);
      return `
        <label class="block text-xs uppercase tracking-wider text-gray-500 mt-3">
          ${window.t('build_quantity', 'Quantity')} ${item.count == null && isQuickSlot(selectedSlot) ? window.t('build_keep', 'KEEP') : current}
          <input class="w-full accent-[#bfa571] mt-2" type="range" min="1" max="${max}" value="${current}" oninput="markBuildEditing(); pendingItem.count=Number(this.value); renderConfigPanel()">
        </label>
      `;
    }

function confirmPendingItem() {
      if (!selectedSlot || !pendingItem) return;
      localBuild.slots[selectedSlot] = { ...pendingItem };
      pendingItem = null;
      markBuildEditing();
      renderEquipmentGrid();
      renderConfigPanel();
    }

function clearSlot(slot) {
      if (isInspectingBuild()) return;
      if (!slot) return;
      localBuild.slots[slot] = null;
      if (selectedSlot === slot) {
        pendingItem = null;
      }
      markBuildEditing();
      renderEquipmentGrid();
      if (selectedSlot === slot) renderConfigPanel();
    }

function applyBuild() {
      if (isInspectingBuild()) {
        copyViewedBuild();
        return;
      }
      const loadStats = document.getElementById('load-with-stats').checked;
      const loadAppCheckbox = document.getElementById('load-with-appearance');
      const loadApp = loadAppCheckbox ? loadAppCheckbox.checked : false;
      const loadEquipCheckbox = document.getElementById('load-with-equipment');
      const loadEquip = loadEquipCheckbox ? loadEquipCheckbox.checked : true;
      fetch('/api/build/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slots: loadEquip ? (localBuild.slots || {}) : null, status: loadStats ? localStatus : null, appearance: loadApp ? localAppearance : null })
      })
        .then(res => res.json())
        .then(data => {
          if (data.loaded) {
            localBuild = data.build || localBuild;
            localStatus = data.status || localStatus;
            localAppearance = data.appearance || localAppearance;
            buildDirty = false;
            const state = document.getElementById('build-edit-state');
            if (state) {
              state.innerText = 'Live Sync';
              state.classList.remove('text-[#bfa571]');
              state.classList.add('text-gray-500');
            }
            renderStatusPanel();
            renderEquipmentGrid();
            renderConfigPanel();
          }
          if (data.message && data.message.includes("Main Menu")) {
            alert(data.message);
          } else {
            console.log(data.message || 'Build applied');
          }
        });
    }

function saveBuildFile() {
      const data = {
        equipment: frontendSlotsToBackendEquipment(localBuild.slots || {}),
        stats: exportStats(localStatus || {}),
        appearance: localAppearance || {},
        shadow_of_erdtree: {
          scadutree_blessing: Number(localStatus.scadutree_blessing || 0),
          revered_spirit_ash_blessing: Number(localStatus.revered_spirit_ash || 0),
        },
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'phantom-build.json';
      link.click();
      URL.revokeObjectURL(link.href);
    }