let inventoryData = [];
let invSelectedEntryIndex = null;
let invPendingItem = null;
let invSearchResults = [];
let invSearchTimer = null;
let invSelectedCategory = "";

function openInventoryTabShell() {
    document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
    const btn = Array.from(document.querySelectorAll('.sidebar-btn')).find(b => b.textContent.trim().toLowerCase() === 'inventory');
    if (btn) btn.classList.add('active');
    activeTab = 'inventory';
    const mainTab = document.getElementById('main-tab'); if(mainTab) mainTab.classList.add('hidden');
    const cheatsTab = document.getElementById('cheats-tab'); if(cheatsTab) cheatsTab.classList.add('hidden');
    const backupTab = document.getElementById('backup-tab'); if(backupTab) backupTab.classList.add('hidden');
    const buildTab = document.getElementById('build-tab'); if(buildTab) buildTab.classList.add('hidden');
    const invTab = document.getElementById('inventory-tab'); if(invTab) invTab.classList.remove('hidden');
    
    refreshInventory();
    loadInvCategories();
}

function refreshInventory() {
    if (activeTab !== 'inventory') return;
    document.getElementById('inventory-grid').innerHTML = '<div class="text-gray-500 text-center w-full text-sm mt-10">Loading inventory...</div>';
    
    fetch('/api/inventory')
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                inventoryData = data.items || [];
                renderInventoryGrid();
            } else {
                document.getElementById('inventory-grid').innerHTML = `<div class="text-red-500 text-center w-full text-sm mt-10">${escapeHtml(data.message || 'Failed to load')}</div>`;
            }
        });
}

function renderInventoryGrid() {
    const grid = document.getElementById('inventory-grid');
    if (!inventoryData.length) {
        grid.innerHTML = '<div class="text-gray-500 text-center w-full text-sm mt-10">No items found in inventory or game not loaded.</div>';
        return;
    }
    
    const searchInput = document.getElementById('inv-item-search');
    const searchQ = (searchInput ? searchInput.value : '').toLowerCase();
    const catInput = document.getElementById('inv-category-filter');
    const catF = catInput ? catInput.value : '';
    
    let filtered = inventoryData;
    if (searchQ) filtered = filtered.filter(i => String(i.name).toLowerCase().includes(searchQ) || String(i.item_id).includes(searchQ));
    if (catF) filtered = filtered.filter(i => i.category === catF);
    
    // Organize by category and name
    filtered.sort((a, b) => {
        if (a.category !== b.category) return (a.category || '').localeCompare(b.category || '');
        return (a.name || '').localeCompare(b.name || '');
    });
    
    if (!filtered.length) {
        grid.innerHTML = '<div class="text-gray-500 text-center w-full text-sm mt-10">No items match your search.</div>';
        return;
    }
    
    const html = filtered.map(item => `
        <div class="flex items-center justify-between p-2 bg-white/5 border border-white/5 rounded hover:bg-white/10 transition-colors cursor-pointer ${invSelectedEntryIndex === item.list_name + '-' + item.index ? 'border-[#bfa571]' : ''}" onclick="selectInvEntry('${item.list_name}-${item.index}')">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-black/40 rounded flex items-center justify-center shrink-0 border border-white/5">
                    ${item.icon_id ? `<img src="/api/icons/${item.icon_id}" class="w-8 h-8 object-contain">` : ''}
                </div>
                <div>
                    <div class="text-sm text-gray-200 fantasy-font uppercase tracking-widest">${escapeHtml(item.name)}</div>
                    <div class="text-[10px] text-gray-500 uppercase tracking-widest">${escapeHtml(item.category)} &middot; ID: ${item.item_id}</div>
                </div>
            </div>
            <div class="text-[#bfa571] font-mono font-bold text-sm bg-black/40 px-3 py-1 rounded border border-white/5">
                x${item.quantity}
            </div>
        </div>
    `).join('');
    
    grid.innerHTML = html;
}

function selectInvEntry(index) {
    invSelectedEntryIndex = index;
    invPendingItem = null;
    renderInventoryGrid();
    renderInvConfigPanel();
}

function clearInvSelection() {
    invSelectedEntryIndex = null;
    invPendingItem = null;
    renderInventoryGrid();
    renderInvConfigPanel();
}

function renderInvConfigPanel() {
    const panel = document.getElementById('inv-config-panel');
    
    if (invPendingItem) {
        // Adding new item
        panel.innerHTML = `
            <div class="flex gap-4">
                <div class="w-20 h-20 soulslike-slot item-glow flex items-center justify-center shrink-0 active">
                    ${invPendingItem.icon_id ? `<img src="/api/icons/${invPendingItem.icon_id}" class="w-16 h-16 object-contain">` : ''}
                </div>
                <div class="flex-1">
                    <h4 class="fantasy-font text-gray-100 uppercase text-base leading-tight">Add: ${escapeHtml(invPendingItem.name)}</h4>
                    <div class="flex justify-between items-center mt-2 border-b border-white/5 pb-1">
                        <span class="text-[10px] text-gray-500 uppercase tracking-widest">ID</span>
                        <span class="text-xs text-[#bfa571] font-bold">${invPendingItem.id}</span>
                    </div>
                </div>
            </div>
            <label class="block text-xs uppercase tracking-wider text-gray-500 mt-4">
                Quantity <span id="inv-add-qty-label" class="text-[#bfa571] ml-2">1</span>
                <input id="inv-add-qty" class="w-full accent-[#bfa571] mt-2" type="range" min="1" max="${invPendingItem.max_num || 99}" value="1" oninput="document.getElementById('inv-add-qty-label').innerText = this.value">
            </label>
            <div class="mt-4 grid grid-cols-2 gap-2">
                <button class="py-2 bg-[#bfa571] text-black fantasy-font uppercase tracking-widest text-xs font-bold hover:brightness-110 rounded" onclick="addInvItem()">Add Item</button>
                <button class="py-2 bg-white/10 text-gray-300 fantasy-font uppercase tracking-widest text-xs font-bold hover:bg-white/20 rounded" onclick="clearInvSelection()">Cancel</button>
            </div>
        `;
        return;
    }
    
    if (invSelectedEntryIndex !== null) {
        const item = inventoryData.find(i => i.list_name + '-' + i.index === invSelectedEntryIndex);
        if (item) {
            panel.innerHTML = `
                <div class="flex gap-4">
                    <div class="w-20 h-20 soulslike-slot item-glow flex items-center justify-center shrink-0 active">
                        ${item.icon_id ? `<img src="/api/icons/${item.icon_id}" class="w-16 h-16 object-contain">` : ''}
                    </div>
                    <div class="flex-1">
                        <h4 class="fantasy-font text-gray-100 uppercase text-base leading-tight">Edit: ${escapeHtml(item.name)}</h4>
                        <div class="flex justify-between items-center mt-2 border-b border-white/5 pb-1">
                            <span class="text-[10px] text-gray-500 uppercase tracking-widest">ID</span>
                            <span class="text-xs text-[#bfa571] font-bold">${item.item_id}</span>
                        </div>
                    </div>
                </div>
                <div class="mt-4 p-3 bg-black/40 border border-[#bfa571]/20 rounded">
                    <label class="block text-xs uppercase tracking-wider text-gray-500 mb-2">
                        Quantity <span id="inv-edit-qty-label" class="text-[#bfa571] ml-2">${item.quantity}</span>
                    </label>
                    <div class="flex items-center gap-2">
                        <input id="inv-edit-qty" type="number" class="build-input w-24 text-center font-mono font-bold" min="0" max="${item.max_num || 99}" value="${item.quantity}" oninput="if(Number(this.value) > ${item.max_num || 99}) this.value = ${item.max_num || 99}; document.getElementById('inv-edit-qty-label').innerText = this.value">
                        <button class="px-4 py-2 bg-[#bfa571] text-black fantasy-font uppercase tracking-widest text-xs font-bold hover:brightness-110 rounded whitespace-nowrap" onclick="saveInvEdit()">Save</button>
                    </div>
                </div>
                <div class="mt-3">
                    <button class="w-full py-2 bg-red-500/10 border border-red-500/30 text-red-400 fantasy-font uppercase tracking-widest text-xs font-bold hover:bg-red-500/20 rounded transition-colors" onclick="removeInvItem()">Remove Item (Qty 0)</button>
                </div>
            `;
            return;
        }
    }
    
    panel.innerHTML = `
        <div class="flex gap-4">
            <div class="w-20 h-20 soulslike-slot item-glow flex items-center justify-center shrink-0 active"></div>
            <div class="flex-1">
                <h4 class="fantasy-font text-gray-100 uppercase text-base leading-tight">Select Item</h4>
                <div class="flex justify-between items-center mt-2 border-b border-white/5 pb-1">
                    <span class="text-[10px] text-gray-500 uppercase tracking-widest">Status</span>
                    <span class="text-xs text-[#bfa571] font-bold">Ready</span>
                </div>
            </div>
        </div>
        <p class="text-xs text-gray-500 mt-4 leading-relaxed">Select an item from the left to edit its quantity, or search below to attempt adding a new item.</p>
    `;
}

function loadInvCategories() {
    fetch('/api/items/categories?all=1')
        .then(res => res.json())
        .then(data => {
            const selectAdd = document.getElementById('inv-category-filter');
            const selectCur = document.getElementById('inv-current-category');
            const cats = data.categories || [];
            const html = '<option value="">ALL CATEGORIES</option>' + cats.map(cat => `<option value="${escapeAttr(cat)}">${escapeHtml(cat)}</option>`).join('');
            
            if (selectAdd) selectAdd.innerHTML = html;
            if (selectCur) selectCur.innerHTML = html;
            
            runInvSearch();
            renderInventoryGrid();
        })
        .catch(() => {
            runInvSearch();
            renderInventoryGrid();
        });
}

function queueInvSearch() {
    clearTimeout(invSearchTimer);
    invSearchTimer = setTimeout(runInvSearch, 300);
}

function runInvSearch() {
    invSelectedCategory = document.getElementById('inv-category-filter').value;
    const q = document.getElementById('inv-item-search').value;
    
    const params = new URLSearchParams({ q, equip_only: '0', limit: '100' });
    if (invSelectedCategory) params.set('category', invSelectedCategory);
    
    fetch('/api/items/search?' + params.toString())
        .then(res => res.json())
        .then(data => {
            invSearchResults = data.items || [];
            document.getElementById('inv-search-results').innerHTML = invSearchResults.map((item, i) => `
                <button title="${escapeAttr(item.name)}" class="aspect-square soulslike-slot flex items-center justify-center transition-all relative cursor-pointer hover:selected-highlight" onclick="selectInvPendingItem(${i})">
                    ${item.icon_id ? `<img src="/api/icons/${item.icon_id}" alt="${escapeAttr(item.name)}" class="w-[85%] h-[85%] object-contain p-1 transition-all">` : `<span class="text-[9px] text-center text-gray-500 p-1">${escapeHtml(item.name)}</span>`}
                </button>
            `).join('') || '<div class="col-span-5 text-xs text-gray-500">No items found.</div>';
            
            renderInventoryGrid();
        });
}

function selectInvPendingItem(index) {
    invPendingItem = invSearchResults[index];
    invSelectedEntryIndex = null;
    renderInvConfigPanel();
}

function saveInvEdit() {
    if (invSelectedEntryIndex === null) return;
    
    const item = inventoryData.find(i => i.list_name + '-' + i.index === invSelectedEntryIndex);
    if (!item) return;

    let qty = Number(document.getElementById('inv-edit-qty').value);
    
    const maxQty = item.max_num || 99;
    if (qty > maxQty) qty = maxQty;
    if (qty < 0) qty = 0;
    
    const list_name = item.list_name;
    const index = item.index;

    fetch('/api/inventory/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: index, list_name: list_name, quantity: qty })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            refreshInventory();
            invSelectedEntryIndex = null;
            renderInvConfigPanel();
        } else {
            alert(data.message || 'Failed to edit inventory');
        }
    });
}

function removeInvItem() {
    if (invSelectedEntryIndex === null) return;
    
    const item = inventoryData.find(i => i.list_name + '-' + i.index === invSelectedEntryIndex);
    if (!item) return;

    const list_name = item.list_name;
    const index = item.index;
    
    fetch('/api/inventory/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: index, list_name: list_name, quantity: 0 })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            refreshInventory();
            invSelectedEntryIndex = null;
            renderInvConfigPanel();
        } else {
            alert(data.message || 'Failed to remove inventory item');
        }
    });
}

function addInvItem() {
    if (!invPendingItem) return;
    const qty = document.getElementById('inv-add-qty').value;
    fetch('/api/inventory/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: invPendingItem.id, global_id: invPendingItem.global_id, quantity: Number(qty), category: invPendingItem.category, max_num: invPendingItem.max_num })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            refreshInventory();
            invPendingItem = null;
            renderInvConfigPanel();
        } else {
            alert(data.message || 'Failed to add item');
        }
    });
}

// Intercept tab switches
const oldOpenTab = window.switchTab;
if (oldOpenTab && !window.invTabHooked) {
    window.switchTab = function(tabName, element) {
        if (tabName === 'inventory') {
            openInventoryTabShell();
            return;
        }
        oldOpenTab.apply(this, arguments);
    };
    window.invTabHooked = true;
} else if (!oldOpenTab) {
    window.switchTab = function(tabName, element) {
        if (tabName === 'inventory') openInventoryTabShell();
        else if (tabName === 'build') {
            if (typeof openBuildTabShell === 'function') {
                openBuildTabShell();
                updateBuild(true);
            }
        }
    }
}
