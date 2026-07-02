document.addEventListener('DOMContentLoaded', () => {
    let settings = {};
    let backups = { pinned: [], regular: [] };
    let selectedBackup = null;
    let autoRunning = false;
    let availableSaveFiles = [];
    let refreshInterval = null;

    // DOM Elements
    const statusMsg = document.getElementById('backup-status-msg');
    const autoBackupIndicator = document.getElementById('auto-backup-indicator');
    const autoBackupDot = document.getElementById('auto-backup-dot');
    const autoBackupText = document.getElementById('auto-backup-text');
    
    const settingsBtn = document.getElementById('backup-settings-btn');
    const refreshBtn = document.getElementById('backup-refresh-btn');
    const createBackupBtn = document.getElementById('create-backup-btn');
    const toggleAutoBtn = document.getElementById('toggle-auto-backup-btn');
    
    const pinnedContainer = document.getElementById('pinned-backups-container');
    const pinnedList = document.getElementById('pinned-backups-list');
    const regularList = document.getElementById('regular-backups-list');
    
    const settingsPanel = document.getElementById('backup-settings-panel');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    
    const selectedDetails = document.getElementById('selected-backup-details');
    const noSelectionView = document.getElementById('no-selection-view');
    const selectedName = document.getElementById('selected-backup-name');
    const selectedDate = document.getElementById('selected-backup-date');
    
    const btnRestore = document.getElementById('btn-restore');
    const btnRename = document.getElementById('btn-rename');
    const btnPin = document.getElementById('btn-pin');
    const btnDelete = document.getElementById('btn-delete');
    
    // Settings inputs
    const setSaveDir = document.getElementById('setting-save-dir');
    const setBackupDir = document.getElementById('setting-backup-dir');
    const setSaveFile = document.getElementById('setting-save-file');
    const setMethod = document.getElementById('setting-method');
    const setIntervalInput = document.getElementById('setting-interval');
    const setMethodLabel = document.getElementById('setting-method-label');
    const setMaxBackups = document.getElementById('setting-max-backups');
    const setMaxBackupsVal = document.getElementById('setting-max-backups-val');
    const setVolume = document.getElementById('setting-volume');
    const setVolumeVal = document.getElementById('setting-volume-val');
    const setSafeLoad = document.getElementById('setting-safeload');
    
    const btnAutoFind = document.getElementById('setting-auto-find');
    const autoFindResults = document.getElementById('auto-find-results');
    const btnBrowseSave = document.getElementById('setting-browse-save');
    const btnBrowseBackup = document.getElementById('setting-browse-backup');

    function showStatus(msg) {
        statusMsg.textContent = msg;
        statusMsg.classList.remove('hidden');
        setTimeout(() => statusMsg.classList.add('hidden'), 3000);
    }

    async function apiCall(url, options = {}) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error('API Error');
            return await res.json();
        } catch (e) {
            console.error(e);
            throw e;
        }
    }

    async function loadSettings() {
        try {
            settings = await apiCall('/api/backup/settings');
            setSaveDir.value = settings.save_directory || '';
            setBackupDir.value = settings.backup_directory || '';
            setMethod.value = settings.backup_method;
            setIntervalInput.value = settings.backup_method == 0 ? settings.auto_backup_interval : settings.sleep_between_saves;
            setMethodLabel.textContent = settings.backup_method == 0 ? 'Mins' : 'Sleep';
            setMaxBackups.value = settings.max_backups;
            setMaxBackupsVal.textContent = settings.max_backups;
            setVolume.value = settings.notification_volume;
            setVolumeVal.textContent = settings.notification_volume + '%';
            setSafeLoad.checked = settings.quit_to_menu_before_load;

            renderKeybinds();

            if (settings.save_directory) {
                await fetchSaveFiles(settings.save_directory, '*');
            } else {
                btnAutoFind.click();
            }
        } catch (e) { }
    }

    async function fetchSaveFiles(dir, ext) {
        try {
            const data = await apiCall(`/api/backup/save-files?save_dir=${encodeURIComponent(dir)}&ext=${encodeURIComponent(ext)}`);
            availableSaveFiles = data.files;
            setSaveFile.innerHTML = '';
            availableSaveFiles.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f;
                opt.textContent = f;
                setSaveFile.appendChild(opt);
            });
            if (settings.save_file_name && availableSaveFiles.includes(settings.save_file_name)) {
                setSaveFile.value = settings.save_file_name;
            } else if (availableSaveFiles.length > 0) {
                setSaveFile.value = availableSaveFiles[0];
                settings.save_file_name = availableSaveFiles[0];
            }
        } catch (e) { }
    }

    async function saveSettings() {
        settings.save_directory = setSaveDir.value;
        settings.backup_directory = setBackupDir.value;
        settings.save_file_name = setSaveFile.value;
        settings.backup_method = parseInt(setMethod.value);
        if (settings.backup_method == 0) {
            settings.auto_backup_interval = parseInt(setIntervalInput.value);
        } else {
            settings.sleep_between_saves = parseInt(setIntervalInput.value);
        }
        settings.max_backups = parseInt(setMaxBackups.value);
        settings.notification_volume = parseInt(setVolume.value);
        settings.quit_to_menu_before_load = setSafeLoad.checked;

        try {
            await apiCall('/api/backup/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            saveSettingsBtn.textContent = 'Settings Saved';
            saveSettingsBtn.classList.replace('bg-[#bfa571]', 'bg-emerald-900/40');
            saveSettingsBtn.classList.replace('text-black', 'text-emerald-400');
            saveSettingsBtn.classList.replace('border-[#bfa571]', 'border-emerald-500');
            setTimeout(() => {
                saveSettingsBtn.textContent = 'Commit Changes';
                saveSettingsBtn.classList.replace('bg-emerald-900/40', 'bg-[#bfa571]');
                saveSettingsBtn.classList.replace('text-emerald-400', 'text-black');
                saveSettingsBtn.classList.replace('border-emerald-500', 'border-[#bfa571]');
            }, 2000);
            if (settings.save_directory) {
                await fetchSaveFiles(settings.save_directory, '*');
            }
        } catch (e) {
            showStatus('Failed to save settings');
        }
    }

    async function loadBackups() {
        try {
            const oldLatest = backups.regular.length > 0 ? backups.regular[0].name : null;
            backups = await apiCall('/api/backup/list');
            const newLatest = backups.regular.length > 0 ? backups.regular[0].name : null;
            
            if ((!selectedBackup && newLatest) || (oldLatest && newLatest && oldLatest !== newLatest)) {
                selectedBackup = newLatest;
                updateSelectedView();
            }
            
            renderBackups();
        } catch (e) { }
    }

    function createCard(entry, isPinned) {
        const isSelected = selectedBackup === entry.name;
        const imgHtml = entry.hasScreenshot 
            ? `<img src="/api/backup/screenshot/${encodeURIComponent(entry.name)}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy" />`
            : `<div class="w-full h-full flex items-center justify-center text-[10px] fantasy-font text-gray-700 tracking-widest">NO PREVIEW</div>`;

        const div = document.createElement('div');
        div.className = `group relative rounded border mb-3 transition-all duration-300 cursor-pointer overflow-hidden ${isSelected ? 'border-[#bfa571] shadow-[0_5px_15px_rgba(191,165,113,0.2)] bg-[#bfa571]/5' : 'border-white/5 hover:border-white/10 bg-black/20'}`;
        div.innerHTML = `
            <div class="h-[100px] w-full bg-black/60 relative">
                ${imgHtml}
                <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent flex flex-col justify-end p-2">
                    <div class="flex justify-between items-end gap-2">
                        <div class="flex-1 min-w-0">
                            <h4 class="text-[10px] fantasy-font tracking-[0.2em] truncate uppercase mb-0.5 ${isSelected ? 'text-[#bfa571]' : 'text-gray-300'}">${entry.name.replace('.zip', '').replace('.sl2', '')}</h4>
                            <span class="text-[8px] text-gray-500 uppercase tracking-widest block">${entry.date}</span>
                            ${entry.sourceFiles ? `<span class="text-[7px] text-[#bfa571]/50 uppercase tracking-widest block truncate mt-0.5">${entry.sourceFiles}</span>` : ''}
                        </div>
                        <button class="pin-btn transition-all p-1 text-xs ${isPinned ? 'text-[#bfa571]' : 'text-gray-600 hover:text-white opacity-40 hover:opacity-100'}">
                            ${isPinned ? '★' : '☆'}
                        </button>
                    </div>
                </div>
            </div>
        `;
        div.onclick = () => {
            selectedBackup = entry.name;
            renderBackups();
            updateSelectedView();
        };
        div.querySelector('.pin-btn').onclick = async (e) => {
            e.stopPropagation();
            try {
                await apiCall(`/api/backup/pin/${encodeURIComponent(entry.name)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pin: !isPinned })
                });
                await loadBackups();
            } catch (err) { }
        };
        return div;
    }

    function renderBackups() {
        pinnedList.innerHTML = '';
        regularList.innerHTML = '';

        if (backups.pinned.length > 0) {
            pinnedContainer.classList.remove('hidden');
            backups.pinned.forEach(b => pinnedList.appendChild(createCard(b, true)));
        } else {
            pinnedContainer.classList.add('hidden');
        }

        if (backups.regular.length > 0) {
            backups.regular.forEach(b => regularList.appendChild(createCard(b, false)));
        } else {
            regularList.innerHTML = `
                <div class="p-10 text-center border border-dashed border-white/5 rounded-lg">
                    <p class="text-gray-600 text-sm italic">No archives found.</p>
                </div>
            `;
        }
    }

    function updateSelectedView() {
        if (!selectedBackup) {
            selectedDetails.classList.add('hidden');
            noSelectionView.classList.remove('hidden');
        } else {
            const all = [...backups.pinned, ...backups.regular];
            const entry = all.find(b => b.name === selectedBackup);
            if (!entry) return;

            selectedDetails.classList.remove('hidden');
            noSelectionView.classList.add('hidden');
            
            selectedName.textContent = entry.name.replace('.zip', '').replace('.sl2', '');
            selectedDate.textContent = entry.date;
            document.getElementById('selected-backup-source').textContent = entry.sourceFiles || '';

            if (entry.hasScreenshot) {
                document.getElementById('selected-backup-img-fallback').classList.add('hidden');
                document.getElementById('selected-backup-img').classList.remove('hidden');
                document.getElementById('selected-backup-img').src = `/api/backup/screenshot/${encodeURIComponent(entry.name)}`;
            } else {
                document.getElementById('selected-backup-img-fallback').classList.remove('hidden');
                document.getElementById('selected-backup-img').classList.add('hidden');
            }
        }
    }

    async function checkAutoStatus() {
        try {
            const data = await apiCall('/api/backup/auto/status');
            autoRunning = data.running;
            if (autoRunning) {
                autoBackupIndicator.classList.replace('bg-red-500/10', 'bg-emerald-500/10');
                autoBackupIndicator.classList.replace('border-red-500/30', 'border-emerald-500/30');
                autoBackupDot.classList.replace('bg-red-500', 'bg-emerald-500');
                autoBackupDot.classList.add('animate-pulse');
                autoBackupText.classList.replace('text-red-400', 'text-emerald-400');
                autoBackupText.textContent = 'Auto-Backup Active';
                autoBackupText.setAttribute('data-i18n', 'bkp_auto_active');
                toggleAutoBtn.textContent = 'Stop Auto';
                toggleAutoBtn.setAttribute('data-i18n', 'bkp_stop_auto');
            } else {
                autoBackupIndicator.classList.replace('bg-emerald-500/10', 'bg-red-500/10');
                autoBackupIndicator.classList.replace('border-emerald-500/30', 'border-red-500/30');
                autoBackupDot.classList.replace('bg-emerald-500', 'bg-red-500');
                autoBackupDot.classList.remove('animate-pulse');
                autoBackupText.classList.replace('text-emerald-400', 'text-red-400');
                autoBackupText.textContent = 'Auto-Backup Inactive';
                autoBackupText.setAttribute('data-i18n', 'bkp_auto_inactive');
                toggleAutoBtn.textContent = 'Start Auto';
                toggleAutoBtn.setAttribute('data-i18n', 'bkp_start_auto');
            }
            if (typeof translateUI === 'function') translateUI();
        } catch (e) { }
    }

    const keybinds = [
        { id: 'keybind_save', label: 'Create Archive' },
        { id: 'keybind_load', label: 'Restore Latest' },
        { id: 'keybind_auto_start', label: 'Start Auto' },
        { id: 'keybind_auto_stop', label: 'Stop Auto' }
    ];

    function renderKeybinds() {
        const keybindContainer = document.getElementById('keybind-container');
        if (!keybindContainer) return;
        keybindContainer.innerHTML = '';
        keybinds.forEach(kb => {
            const div = document.createElement('div');
            div.className = 'flex flex-col';
            let displayVal = settings[kb.id] || 'NONE';
            div.innerHTML = `
                <label class="text-[10px] text-gray-500 mb-1 uppercase tracking-widest fantasy-font font-bold" data-i18n="${kb.id}">${kb.label}</label>
                <div class="flex gap-2">
                    <input type="text" id="kb-input-${kb.id}" readonly value="${displayVal}"
                        class="flex-1 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-xs text-gray-200 focus:outline-none cursor-pointer fantasy-font tracking-widest transition-all" />
                    <button id="kb-clear-${kb.id}" class="px-2 bg-white/5 border border-white/10 rounded-sm text-gray-500 hover:text-red-400 transition-colors" title="Clear">✕</button>
                </div>
            `;
            keybindContainer.appendChild(div);
            
            const input = document.getElementById(`kb-input-${kb.id}`);
            const clearBtn = document.getElementById(`kb-clear-${kb.id}`);
            let recording = false;
            
            input.onclick = () => {
                recording = true;
                input.value = 'PRESS KEYS...';
                input.classList.replace('border-white/10', 'border-[#bfa571]');
            };
            
            input.onblur = () => {
                recording = false;
                input.value = settings[kb.id] || 'NONE';
                input.classList.replace('border-[#bfa571]', 'border-white/10');
            };
            
            input.onkeydown = (e) => {
                if (!recording) return;
                e.preventDefault();
                e.stopPropagation();
                if (e.key === 'Escape') {
                    input.blur();
                    return;
                }
                if (e.key === 'Backspace' || e.key === 'Delete') {
                    settings[kb.id] = '';
                    settings[`${kb.id}_vks`] = [];
                    input.blur();
                    return;
                }
                
                const modifiers = [];
                const vks = [];
                
                if (e.ctrlKey) { modifiers.push('ctrl'); vks.push(17); }
                if (e.shiftKey) { modifiers.push('shift'); vks.push(16); }
                if (e.altKey) { modifiers.push('alt'); vks.push(18); }
                
                let key = e.key.toLowerCase();
                if (!['control', 'shift', 'alt'].includes(key)) {
                    if (key === ' ') key = 'space';
                    modifiers.push(key);
                    vks.push(e.keyCode);
                }
                
                settings[kb.id] = modifiers.join('+');
                settings[`${kb.id}_vks`] = vks;
                input.blur();
            };
            
            clearBtn.onclick = () => {
                settings[kb.id] = '';
                settings[`${kb.id}_vks`] = [];
                input.value = 'NONE';
            };
        });
        if (typeof translateUI === 'function') translateUI();
    }

    // Event Listeners
    settingsBtn.onclick = () => {
        const isHidden = settingsPanel.classList.contains('hidden');
        if (isHidden) {
            settingsPanel.classList.remove('hidden');
            settingsPanel.classList.add('flex');
            settingsBtn.classList.add('bg-[#bfa571]', 'text-black', 'border-[#bfa571]');
            settingsBtn.classList.remove('bg-black/40', 'text-gray-500');
            settingsBtn.textContent = 'Close Settings';
        } else {
            settingsPanel.classList.add('hidden');
            settingsPanel.classList.remove('flex');
            settingsBtn.classList.remove('bg-[#bfa571]', 'text-black', 'border-[#bfa571]');
            settingsBtn.classList.add('bg-black/40', 'text-gray-500');
            settingsBtn.textContent = 'Settings';
        }
    };

    closeSettingsBtn.onclick = settingsBtn.onclick;
    saveSettingsBtn.onclick = saveSettings;
    refreshBtn.onclick = loadBackups;

    createBackupBtn.onclick = async () => {
        showStatus('Creating backup...');
        createBackupBtn.disabled = true;
        try {
            await apiCall('/api/backup/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ requestSave: true })
            });
            showStatus('Backup created');
            await loadBackups();
        } catch (e) {
            showStatus('Failed to create backup');
        } finally {
            createBackupBtn.disabled = false;
        }
    };

    toggleAutoBtn.onclick = async () => {
        try {
            if (autoRunning) {
                await apiCall('/api/backup/auto/stop', { method: 'POST' });
            } else {
                await apiCall('/api/backup/auto/start', { method: 'POST' });
            }
            await checkAutoStatus();
        } catch (e) { }
    };

    btnAutoFind.onclick = async () => {
        try {
            const data = await apiCall('/api/backup/auto-find');
            if (data.paths.length === 0) {
                showStatus('No save locations found');
            } else if (data.paths.length === 1) {
                setSaveDir.value = data.paths[0].path;
                showStatus(`Found: ${data.paths[0].path}`);
                await fetchSaveFiles(setSaveDir.value, '*');
            } else {
                autoFindResults.innerHTML = '';
                data.paths.forEach(r => {
                    const btn = document.createElement('button');
                    btn.className = 'w-full text-left px-4 py-2 hover:bg-[#bfa571]/10 text-xs text-gray-400 hover:text-[#bfa571] transition-all flex items-center gap-2';
                    btn.innerHTML = `<span class="text-[#bfa571] font-bold">${r.game}</span> ${r.path}`;
                    btn.onclick = async () => {
                        setSaveDir.value = r.path;
                        autoFindResults.classList.add('hidden');
                        await fetchSaveFiles(setSaveDir.value, '*');
                    };
                    autoFindResults.appendChild(btn);
                });
                autoFindResults.classList.remove('hidden');
            }
        } catch (e) {
            showStatus('Auto-find failed');
        }
    };

    
    // --- Custom Web File Picker Logic ---
    const modal = document.getElementById('file-picker-modal');
    const modalClose = document.getElementById('file-picker-close');
    const modalCancel = document.getElementById('file-picker-cancel');
    const modalSelect = document.getElementById('file-picker-select');
    const modalUp = document.getElementById('file-picker-up');
    const modalPath = document.getElementById('file-picker-path');
    const modalGrid = document.getElementById('file-picker-grid');
    const modalDrives = document.getElementById('file-picker-drives');
    const modalStatus = document.getElementById('file-picker-status');
    const modalLoading = document.getElementById('file-picker-loading');

    let currentPickerTarget = null;
    let currentPath = "";

    async function loadDirectory(path) {
        modalLoading.classList.remove('hidden');
        modalStatus.textContent = "Loading...";
        try {
            const data = await apiCall('/api/backup/api/fs/list', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });

            if (data.error) {
                modalStatus.textContent = "Error: " + data.error;
            } else {
                currentPath = data.current;
                modalPath.value = currentPath || "This PC";
                modalStatus.textContent = `${data.folders.length} items`;
                
                // Render Drives if we are at root
                if (!currentPath && data.drives) {
                    modalDrives.innerHTML = '<h4 class="text-[10px] fantasy-font text-gray-500 tracking-widest uppercase mb-2">Drives</h4>';
                    data.drives.forEach(drive => {
                        const dBtn = document.createElement('button');
                        dBtn.className = "text-left px-3 py-2 text-xs text-gray-300 hover:bg-white/10 hover:text-white rounded-sm flex items-center gap-2";
                        dBtn.innerHTML = `<span>🖴</span> <span>${drive}</span>`;
                        dBtn.onclick = () => loadDirectory(drive);
                        modalDrives.appendChild(dBtn);
                    });
                }

                // Render Folders
                modalGrid.innerHTML = "";
                if (!currentPath && data.drives) {
                     data.drives.forEach(drive => {
                        const fDiv = document.createElement('div');
                        fDiv.className = "flex flex-col items-center justify-center p-4 bg-white/5 border border-white/5 rounded-md hover:bg-white/10 hover:border-[#bfa571]/50 cursor-pointer transition-all text-center gap-2 group";
                        fDiv.innerHTML = `<span class="text-3xl group-hover:scale-110 transition-transform">🖴</span><span class="text-xs text-gray-300 truncate w-full" title="${drive}">${drive}</span>`;
                        fDiv.onclick = () => loadDirectory(drive);
                        modalGrid.appendChild(fDiv);
                    });
                } else {
                    data.folders.forEach(folder => {
                        const fDiv = document.createElement('div');
                        fDiv.className = "flex flex-col items-center justify-center p-4 bg-white/5 border border-white/5 rounded-md hover:bg-white/10 hover:border-[#bfa571]/50 cursor-pointer transition-all text-center gap-2 group";
                        if (folder.hidden) fDiv.style.opacity = "0.5";
                        fDiv.innerHTML = `<span class="text-4xl text-[#bfa571] group-hover:scale-110 transition-transform">📁</span><span class="text-xs text-gray-300 truncate w-full font-mono" title="${folder.name}">${folder.name}</span>`;
                        fDiv.onclick = () => loadDirectory(folder.path);
                        modalGrid.appendChild(fDiv);
                    });
                }

                // Up Button
                modalUp.onclick = () => {
                    if (data.parent !== undefined) {
                        loadDirectory(data.parent);
                    }
                };
            }
        } catch (e) {
            modalStatus.textContent = "Failed to load directory.";
        }
        modalLoading.classList.add('hidden');
    }

    function openPicker(targetInput) {
        currentPickerTarget = targetInput;
        modal.classList.remove('hidden');
        loadDirectory(targetInput.value || "");
    }

    function closePicker() {
        modal.classList.add('hidden');
        currentPickerTarget = null;
    }

    modalClose.onclick = closePicker;
    modalCancel.onclick = closePicker;

    modalSelect.onclick = async () => {
        if (currentPickerTarget && currentPath) {
            currentPickerTarget.value = currentPath;
            if (currentPickerTarget === setSaveDir) {
                await fetchSaveFiles(setSaveDir.value, '*');
            }
        }
        closePicker();
    };

    btnBrowseSave.onclick = () => openPicker(setSaveDir);
    btnBrowseBackup.onclick = () => openPicker(setBackupDir);


    setMethod.onchange = () => {
        setMethodLabel.textContent = setMethod.value == 0 ? 'Mins' : 'Sleep';
        setIntervalInput.value = setMethod.value == 0 ? settings.auto_backup_interval : settings.sleep_between_saves;
    };
    
    setMaxBackups.oninput = () => setMaxBackupsVal.textContent = setMaxBackups.value;
    setVolume.oninput = () => setVolumeVal.textContent = setVolume.value + '%';

    // Actions
    btnRestore.onclick = async () => {
        if (!selectedBackup) return;
        const msg = settings.quit_to_menu_before_load 
            ? "Safe Load Active: This will return you to the Main Menu and restore." 
            : "WARNING: You should be in the Main Menu before loading a save!";
        if (!confirm(`${msg}\n\nRestore "${selectedBackup}" now?`)) return;
        
        showStatus('Restoring...');
        try {
            await apiCall(`/api/backup/load?name=${encodeURIComponent(selectedBackup)}`, { method: 'POST' });
            showStatus(`Restored: ${selectedBackup}`);
        } catch (e) {
            showStatus('Restore failed');
        }
    };

    btnDelete.onclick = async () => {
        if (!selectedBackup) return;
        if (!confirm(`Are you sure you want to delete "${selectedBackup}"?`)) return;
        try {
            await apiCall(`/api/backup/${encodeURIComponent(selectedBackup)}`, { method: 'DELETE' });
            selectedBackup = null;
            showStatus('Deleted archive');
            await loadBackups();
            updateSelectedView();
        } catch (e) {
            showStatus('Delete failed');
        }
    };

    btnPin.onclick = async () => {
        if (!selectedBackup) return;
        const isPinned = backups.pinned.some(b => b.name === selectedBackup);
        try {
            await apiCall(`/api/backup/pin/${encodeURIComponent(selectedBackup)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: !isPinned })
            });
            await loadBackups();
        } catch (e) { }
    };

    btnRename.onclick = async () => {
        if (!selectedBackup) return;
        const newName = prompt(window.t('bkp_prompt_new_name', 'New name:'), selectedBackup.replace('.zip', '').replace('.sl2', ''));
        if (!newName || newName === selectedBackup.replace('.zip', '').replace('.sl2', '')) return;
        try {
            await apiCall('/api/backup/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ oldName: selectedBackup, newName })
            });
            selectedBackup = newName.endsWith('.sl2') ? newName : `${newName}.sl2`;
            await loadBackups();
            updateSelectedView();
        } catch (e) {
            showStatus('Rename failed');
        }
    };

    // Global hotkeys are now handled entirely by the Python backend via GetAsyncKeyState

    // Init
    loadSettings();
    loadBackups();
    checkAutoStatus();
    
    refreshInterval = setInterval(() => {
        loadBackups();
        checkAutoStatus();
    }, 2000);
});
