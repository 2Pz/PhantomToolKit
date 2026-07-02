let activeTab = 'main';
    let locales = {};
    let currentLang = 'en';

    window.t = function(key, fallback) {
        if (locales && locales[key]) return locales[key];
        return fallback || key;
    };

    window.showSystemMessage = function(msg, isError = false) {
      const toast = document.getElementById('system-message-toast');
      const text = document.getElementById('system-message-text');
      if (!toast || !text) return;
      
      text.innerText = msg;
      if (isError) {
        toast.classList.replace('border-[#bfa571]/50', 'border-red-500/50');
        toast.classList.replace('text-[#bfa571]', 'text-red-400');
      } else {
        toast.classList.replace('border-red-500/50', 'border-[#bfa571]/50');
        toast.classList.replace('text-red-400', 'text-[#bfa571]');
      }
      
      toast.classList.remove('opacity-0', '-translate-y-4');
      toast.classList.add('opacity-100', 'translate-y-0');
      
      if (window.sysMsgTimeout) clearTimeout(window.sysMsgTimeout);
      window.sysMsgTimeout = setTimeout(() => {
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', '-translate-y-4');
      }, 3000);
    };

    function loadLanguageData() {
      fetch('/api/settings/language')
        .then(r => r.json())
        .then(data => {
          currentLang = data.language || 'en';
          fetchLocalesList();
        })
        .catch(() => {
          fetchLocalesList();
        });
    }

    function fetchLocalesList() {
      fetch('/api/locales')
        .then(r => r.json())
        .then(data => {
          const select = document.getElementById('language-select');
          if (select) {
            select.innerHTML = '';
            data.locales.forEach(l => {
              const opt = document.createElement('option');
              const code = l.code || l;
              const name = l.name || (typeof l === 'string' ? l.toUpperCase() : code.toUpperCase());
              
              opt.value = code;
              opt.textContent = name;
              if (code === currentLang) opt.selected = true;
              select.appendChild(opt);
            });
          }
          applyLanguage(currentLang);
        });
    }

    function applyLanguage(lang) {
      fetch(`/static/local/${lang}.json`)
        .then(r => {
            if(!r.ok) throw new Error('not found');
            return r.json();
        })
        .then(data => {
          locales = data;
          translateUI();
        })
        .catch(() => {
           if(lang !== 'en') applyLanguage('en');
        });
    }

    function changeLanguage(lang) {
      currentLang = lang;
      fetch('/api/settings/language', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: lang })
      }).then(() => {
        applyLanguage(lang);
        if (activeTab === 'build' && typeof updateBuild === 'function') {
          updateBuild(true);
        }
      });
    }

    function translateUI() {
      const fontFantasy = locales['app_font_fantasy'] || locales['app_font'] || "'Cinzel', serif";
      const fontBody = locales['app_font_body'] || locales['app_font'] || "'Inter', sans-serif";
      
      document.body.style.fontFamily = fontBody;
      let styleEl = document.getElementById('dynamic-font-style');
      if (!styleEl) {
          styleEl = document.createElement('style');
          styleEl.id = 'dynamic-font-style';
          document.head.appendChild(styleEl);
      }
      styleEl.innerHTML = `
          .fantasy-font, h1, h2, h3 { font-family: ${fontFantasy} !important; }
          body, .inter-font { font-family: ${fontBody} !important; }
      `;

      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (locales[key]) {
            if(el.tagName === 'INPUT' && el.type === 'button') el.value = locales[key];
            else if(el.tagName === 'INPUT' && el.type === 'text' && el.placeholder) el.placeholder = locales[key];
            else el.innerText = locales[key];
        }
      });
    }

    let localBuild = { slots: {} };
    let localStatus = {};
    let localAppearance = null;
    let selectedSlot = null;
    let hoveredSlot = null;
    let pendingItem = null;
    let selectedCategory = '';
    let buildDirty = false;
    let searchTimer = null;
    let ashSearchTimer = null;
    let autoCalcLevel = false;
    let searchResults = [];
    let ashResults = [];
    let ashQuery = '';
    let ashSearchSeq = 0;
    let inspectingSteamId = null;
    let inspectingPlayerIndex = null;
    let inspectingCachedBuild = false;
    let inspectingName = '';
    let recentPlayers = [];
    let cheatsState = {
      noDead: false,
      noDamage: false,
      noHit: false,
      noWeight: false,
      noGoods: false,
      noStamina: false,
      noFP: false,
      noArrow: false
    };

    const attributes = ['vigor', 'mind', 'endurance', 'strength', 'dexterity', 'intelligence', 'faith', 'arcane'];
    const slotGroups = [
      { title: 'Right Hand Armament', slots: [['weapon_r_1', 'R1'], ['weapon_r_2', 'R2'], ['weapon_r_3', 'R3']] },
      { title: 'Left Hand Armament', slots: [['weapon_l_1', 'L1'], ['weapon_l_2', 'L2'], ['weapon_l_3', 'L3']] },
      { title: 'Ammo', slots: [['ammo_1_1', 'Arrow 1'], ['ammo_1_2', 'Arrow 2'], ['ammo_2_1', 'Bolt 1'], ['ammo_2_2', 'Bolt 2']] },
      { title: 'Armor', slots: [['head', 'Head'], ['chest', 'Chest'], ['hands', 'Hands'], ['legs', 'Legs']] },
      { title: 'Talismans', slots: [['talisman_1', 'Talisman 1'], ['talisman_2', 'Talisman 2'], ['talisman_3', 'Talisman 3'], ['talisman_4', 'Talisman 4']] },
      { title: 'Spells', slots: Array.from({length: 14}, (_, i) => [`spell_${i + 1}`, `Spell ${i + 1}`]) },
      { title: 'Quick Items', slots: [...Array.from({length: 5}, (_, i) => [`quick_1_${i + 1}`, `Quick ${i + 1}`]), ...Array.from({length: 5}, (_, i) => [`quick_2_${i + 6}`, `Quick ${i + 6}`])] },
      { title: 'Special', slots: [['physick_tear_1', 'Physick 1'], ['physick_tear_2', 'Physick 2'], ['great_rune', 'Great Rune']] },
    ];

    function switchTab(tab, element) {
      activeTab = tab;
      document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
      element.classList.add('active');

      document.getElementById('main-tab').classList.add('hidden');
      document.getElementById('build-tab').classList.add('hidden');
      document.getElementById('cheats-tab').classList.add('hidden');
      document.getElementById('backup-tab').classList.add('hidden');
      document.getElementById('inventory-tab').classList.add('hidden');

      if (tab === 'main') {
        document.getElementById('main-tab').classList.remove('hidden');
      } else if (tab === 'build') {
        document.getElementById('build-tab').classList.remove('hidden');
        if (!buildDirty) updateBuild(false);
      } else if (tab === 'cheats') {
        document.getElementById('cheats-tab').classList.remove('hidden');
        renderCheats();
      } else if (tab === 'backup') {
        document.getElementById('backup-tab').classList.remove('hidden');
      } else if (tab === 'inventory') {
        document.getElementById('inventory-tab').classList.remove('hidden');
      }
    }





































































        





     





                                        


















                                                                          




                                                                            







                                           







                      



                                                                              





                                                                    


                                                                

















                                                                       

































                




                                                          


                                                                                



                                                    














                                                                                            





                                                       




                                                                                         









                                                                                           




































                                   
















             




                                             













                                                                       

                                                                                         




                                             
















                     






                                     






                                                                      


                                  













                                                                        












































                                       












                                                                                                




















                                                                                            

    function renderAshResults() {
      return ashResults.map(item => {
        const isSelected = pendingItem && pendingItem.ash_of_war === item.id;
        const extraClass = isSelected ? 'border-[#bfa571] border-2 shadow-[0_0_10px_rgba(191,165,113,0.5)] selected-ash-btn' : 'border-transparent';
        return `
        <button title="${escapeAttr(item.name)}" class="soulslike-slot min-h-[54px] rounded p-1 text-[10px] flex items-center justify-center transition-all ${extraClass}" onclick="selectAshOfWar(${item.id})">
          ${item.icon_id ? `<img src="/api/icons/${item.icon_id}" alt="${escapeAttr(item.name)}" class="w-[85%] h-[85%] object-contain">` : `<span>${escapeHtml(item.name)}</span>`}
        </button>
      `}).join('');
    }








                                                                       







                                                                           

    function queueAshSearch() {
      markBuildEditing();
      clearTimeout(ashSearchTimer);
      ashSearchTimer = setTimeout(runAshSearch, 300);
    }











                                         




                                                                    



                                                         

    function clearSelectedSlot() {
      if (isInspectingBuild()) return;
      const slot = hoveredSlot || selectedSlot;
      clearSlot(slot);
    }




                 















              








                  

    function saveBuildToServer() {
      const name = prompt(window.t("build_prompt_name", "Enter a name for this build:"), localStatus.name || "my-build");
      if (!name) return;
      const data = {
        equipment: frontendSlotsToBackendEquipment(localBuild.slots || {}),
        stats: exportStats(localStatus || {}),
        appearance: localAppearance || {},
        shadow_of_erdtree: {
          scadutree_blessing: Number(localStatus.scadutree_blessing || 0),
          revered_spirit_ash_blessing: Number(localStatus.revered_spirit_ash || 0),
        },
      };
      fetch('/api/builds/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, data: data })
      })
        .then(res => res.json())
        .then(res => {
          if (res.message) {
            let m = res.message;
            if (m.startsWith('Saved as ')) m = window.t('sys_saved_as', 'Saved as ') + m.substring(9);
            else m = window.t(m, m);
            window.showSystemMessage(m);
          }
        });
    }

    function loadBuildFromServer() {
      fetch('/api/builds/list')
        .then(res => res.json())
        .then(data => {
          if (!data.builds || data.builds.length === 0) {
            window.showSystemMessage(window.t("No builds found in the builds directory.", "No builds found in the builds directory."));
            return;
          }
          const container = document.getElementById('build-list-container');
          container.innerHTML = '';
          data.builds.forEach(buildName => {
            const btn = document.createElement('button');
            btn.className = "w-full text-left px-4 py-3 rounded bg-black/40 hover:bg-[#bfa571]/20 border border-white/5 hover:border-[#bfa571]/50 text-gray-300 hover:text-white transition-all inter-font text-sm flex justify-between items-center";
            btn.innerHTML = `<span>${buildName.replace('.json', '')}</span> <span class="text-[10px] text-gray-500 uppercase">Load</span>`;
            btn.onclick = () => {
              document.getElementById('build-modal').classList.add('hidden');
              document.getElementById('build-modal').classList.remove('flex');
              
              fetch(`/api/builds/load/${encodeURIComponent(buildName)}`)
                .then(res => res.json())
                .then(result => {
                    if (!result.success) {
                      window.showSystemMessage(window.t(result.message || 'sys_invalid_build', result.message || 'Invalid build file'), true);
                      return;
                    }
                    localBuild = result.build || { slots: {} };
                    if (document.getElementById('load-with-stats').checked) localStatus = result.status || {};
                    const appCheckbox = document.getElementById('load-with-appearance');
                    if (appCheckbox && appCheckbox.checked) localAppearance = result.appearance || null;
                    markBuildEditing();
                    renderStatusPanel();
                    renderEquipmentGrid();
                    renderConfigPanel();
                });
            };
            container.appendChild(btn);
          });
          const modal = document.getElementById('build-modal');
          modal.classList.remove('hidden');
          modal.classList.add('flex');
        })
        .catch(err => {
          console.error("Failed to list builds:", err);
          alert("Error connecting to server.");
        });
    }

    function loadBuildFile(event) {
      const file = event.target.files ? event.target.files[0] : undefined;
      if (!file) return;
      file.text().then(text => {
        const data = JSON.parse(text);
        if (!data.equipment || typeof data.equipment !== 'object') {
          console.error('Invalid build file: expected equipment object');
          return;
        }
        fetch('/api/build/inspect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        })
          .then(res => res.json())
          .then(result => {
            if (!result.success) {
              console.error(result.message || 'Invalid build file');
              return;
            }
            localBuild = result.build || { slots: {} };
            if (document.getElementById('load-with-stats').checked) localStatus = result.status || {};
            const appCheckbox = document.getElementById('load-with-appearance');
            if (appCheckbox && appCheckbox.checked) localAppearance = result.appearance || null;
            markBuildEditing();
            renderStatusPanel();
            renderEquipmentGrid();
            renderConfigPanel();
          });
      });
      event.target.value = '';
    }

    function frontendSlotsToBackendEquipment(slots) {
      const out = {};
      Object.entries(frontendToBackendSlotMap()).forEach(([frontendKey, backendKey]) => {
        out[backendKey] = exportSlotValue(frontendKey, slots[frontendKey]);
      });
      return out;
    }

    function frontendToBackendSlotMap() {
      const map = {
        weapon_r_1: 'primary_right_wep',
        weapon_r_2: 'secondary_right_wep',
        weapon_r_3: 'tertiary_right_wep',
        weapon_l_1: 'primary_left_wep',
        weapon_l_2: 'secondary_left_wep',
        weapon_l_3: 'tertiary_left_wep',
        ammo_1_1: 'primary_arrow',
        ammo_1_2: 'secondary_arrow',
        ammo_2_1: 'primary_bolt',
        ammo_2_2: 'secondary_bolt',
        head: 'helmet',
        chest: 'armor',
        hands: 'gauntlet',
        legs: 'leggings',
        talisman_1: 'accessory_1',
        talisman_2: 'accessory_2',
        talisman_3: 'accessory_3',
        talisman_4: 'accessory_4',
        physick_tear_1: 'physick_tear_1',
        physick_tear_2: 'physick_tear_2',
        great_rune: 'great_rune',
      };
      for (let i = 1; i <= 5; i++) map[`quick_1_${i}`] = `quick_item_${i}`;
      for (let i = 6; i <= 10; i++) map[`quick_2_${i}`] = `quick_item_${i}`;
      for (let i = 1; i <= 14; i++) map[`spell_${i}`] = `magic_slot_${i - 1}`;
      return map;
    }

    function exportSlotValue(frontendKey, item) {
      if (!item || item.id === undefined || item.id === null) return -1;
      const itemId = exportEffectiveItemId(frontendKey, item);
      const out = { id: itemId };
      if (item.count !== undefined && item.count !== null) out.count = Number(item.count);
      if (item.ash_of_war && item.ash_of_war !== -1) out.ash_of_war = Number(item.ash_of_war);
      return Object.keys(out).length === 1 ? out.id : out;
    }

    function exportEffectiveItemId(frontendKey, item) {
      const id = Number(item.id);
      const upgrade = Number(item.upgrade || 0);
      if (frontendKey && frontendKey.startsWith('weapon_') && upgrade > 0) {
        return (id - (id % 100)) + upgrade;
      }
      return id;
    }

    function exportStats(status) {
      return {
        vigor: Number(status.vigor || 0),
        mind: Number(status.mind || 0),
        endurance: Number(status.endurance || 0),
        strength: Number(status.strength || 0),
        dexterity: Number(status.dexterity || 0),
        intelligence: Number(status.intelligence || 0),
        faith: Number(status.faith || 0),
        arcane: Number(status.arcane || 0),
        level: Number(status.level || 0),
        max_hp: Number(status.max_hp || 0),
      };
    }

    document.addEventListener('keydown', event => {
      if (event.key.toLowerCase() !== 'r') return;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
      if (activeTab === 'build') clearSelectedSlot();
    });

    function isWeaponSlot(slot) { return slot && slot.startsWith('weapon_'); }
    function isQuickSlot(slot) { return slot && slot.startsWith('quick_'); }
    function isAmmoSlot(slot) { return slot && slot.startsWith('ammo_'); }
    function isInspectingBuild() { return Boolean(inspectingSteamId || inspectingPlayerIndex !== null || inspectingCachedBuild); }
    function slotLabel(slot) { return slot ? slot.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Slot'; }
    function labelFor(key) { return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()); }
    function escapeHtml(value) {
      return String(value != null ? value : '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    function escapeAttr(value) { return escapeHtml(value).replace(/`/g, '&#96;'); }

    window.initApp = function() {
      try {
        var req = new XMLHttpRequest();
        req.open('GET', '/error_log/INIT_APP_STARTED', true);
        req.send();
      } catch(e) {}
      
      loadLanguageData();

      setInterval(updateStats, 1000);
      setInterval(() => updateBuild(false), 1000);
      updateStats();
      if (typeof renderStatusPanel === 'function') renderStatusPanel();
      if (typeof renderEquipmentGrid === 'function') renderEquipmentGrid();
      if (typeof renderConfigPanel === 'function') renderConfigPanel();
      if (typeof renderCheats === 'function') renderCheats();
    };
    
    const cheatList = [
      { key: 'noDead', label: 'No Dead', desc: 'Prevents HP from reaching zero.' },
      { key: 'noDamage', label: 'No Damage', desc: 'Completely negates incoming damage.' },
      { key: 'noHit', label: 'No Hit', desc: 'Enemies cannot hit or target you.' },
      { key: 'noWeight', label: 'No Weight', desc: 'Sets equip load to zero for fast rolling.' },
      { key: 'noStamina', label: 'No Stamina', desc: 'Actions do not consume stamina.' },
      { key: 'noFP', label: 'No FP', desc: 'Spells and skills cost 0 FP.' },
      { key: 'noGoods', label: 'No Goods', desc: 'Items are never consumed upon use.' },
      { key: 'noArrow', label: 'No Arrow', desc: 'Arrows and bolts are never consumed.' },
    ];















                                                                    








                                                                                   