function updateStats() {
      fetch('/api/stats')
        .then(res => res.json())
        .then(data => {

          const statusEl = document.getElementById('status-text');
          const tbody = document.getElementById('current-players-body');
          const recentTbody = document.getElementById('recent-players-body');
          recentPlayers = data.recent_players || [];

          if (data.recent_players && data.recent_players.length > 0) {
            let recentHtml = '';
            data.recent_players.forEach((p, idx) => {
              let roleBadge = '';

              const lastSeenDate = new Date(p.last_seen * 1000);
              const lastSeenStr = lastSeenDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

              recentHtml += `
                <tr class="cursor-pointer transition-colors hover:bg-white/5" onclick="inspectRecentPlayer(${idx})">
                  <td>
                    <div class="flex items-center font-bold text-gray-400">
                      ${p.name}
                      ${roleBadge}
                    </div>
                    ${p.steam_id ? `
                    <div class="mt-0.5 flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors w-fit group" onclick="event.stopPropagation(); window.open('https://steamcommunity.com/profiles/${p.steam_id}', '_blank')" title="Open Steam Profile: ${p.steam_id}">
                      <svg class="w-3 h-3 opacity-70 group-hover:opacity-100" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M11.979 0C5.362 0 0 5.363 0 11.979c0 4.265 2.213 8.016 5.565 10.155l3.56-5.115c-.217-.674-.334-1.396-.334-2.146 0-3.692 2.993-6.685 6.686-6.685 3.692 0 6.685 2.993 6.685 6.685 0 3.693-2.993 6.686-6.685 6.686-1.503 0-2.887-.497-4.004-1.332l-5.006 3.428c1.642.868 3.513 1.365 5.495 1.365 6.616 0 11.979-5.363 11.979-11.979C23.958 5.363 18.595 0 11.979 0zm4.568 8.083c-1.854 0-3.356 1.503-3.356 3.357 0 1.854 1.502 3.356 3.356 3.356 1.854 0 3.357-1.502 3.357-3.356 0-1.854-1.503-3.357-3.357-3.357zm0 5.176c-1.004 0-1.819-.815-1.819-1.819 0-1.004.815-1.819 1.819-1.819 1.004 0 1.819.815 1.819 1.819 0 1.004-.815 1.819-1.819 1.819zM6.924 15.65c-1.258 0-2.278 1.021-2.278 2.279 0 1.258 1.02 2.278 2.278 2.278 1.258 0 2.278-1.02 2.278-2.278 0-1.258-1.02-2.279-2.278-2.279zm0 3.645c-.754 0-1.366-.612-1.366-1.366 0-.754.612-1.366 1.366-1.366.754 0 1.366.612 1.366 1.366 0 .754-.612 1.366-1.366 1.366z"/>
                      </svg>
                      <span class="font-mono tracking-wider">${p.steam_id}</span>
                    </div>
                    ` : ''}
                  </td>
                  <td class="text-center font-semibold text-gray-500">${p.level}</td>
                  <td class="text-center font-semibold text-gray-500">${lastSeenStr}</td>
                </tr>
              `;
            });
            recentTbody.innerHTML = recentHtml;
          } else {
            recentTbody.innerHTML = '<tr><td colspan="3" class="text-center text-gray-500 py-4">No recent players tracked yet.</td></tr>';
          }

          if (data.loaded && data.players && data.players.length > 0) {
            statusEl.innerText = 'Game Connected';
            statusEl.style.color = '#bfa571';

            let html = '';
            data.players.forEach((p, idx) => {
              const hpPercent = Math.max(0, Math.min(100, (p.hp / Math.max(1, p.max_hp)) * 100));

              let rowClass = 'hover:bg-white/5';
              let roleBadge = '';

              if (p.is_local) {
                rowClass = 'player-row-current';
                roleBadge = '<span class="ml-2 text-[9px] bg-blue-900/50 text-blue-200 px-1.5 py-0.5 rounded border border-blue-700">LOCAL</span>';
              }

              html += `
                <tr class="cursor-pointer transition-colors ${rowClass}" onclick='inspectPlayer(${p.steam_id || 0}, ${p.player_index ?? idx}, ${escapeHtml(JSON.stringify(p.name || ''))}, ${p.is_local ? 'true' : 'false'})'>
                  <td>
                    <div class="flex items-center font-bold text-[#bfa571]">
                      ${p.name}
                      ${roleBadge}
                    </div>
                    ${p.steam_id ? `
                    <div class="mt-0.5 flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors w-fit group" onclick="event.stopPropagation(); window.open('https://steamcommunity.com/profiles/${p.steam_id}', '_blank')" title="Open Steam Profile: ${p.steam_id}">
                      <svg class="w-3 h-3 opacity-70 group-hover:opacity-100" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M11.979 0C5.362 0 0 5.363 0 11.979c0 4.265 2.213 8.016 5.565 10.155l3.56-5.115c-.217-.674-.334-1.396-.334-2.146 0-3.692 2.993-6.685 6.686-6.685 3.692 0 6.685 2.993 6.685 6.685 0 3.693-2.993 6.686-6.685 6.686-1.503 0-2.887-.497-4.004-1.332l-5.006 3.428c1.642.868 3.513 1.365 5.495 1.365 6.616 0 11.979-5.363 11.979-11.979C23.958 5.363 18.595 0 11.979 0zm4.568 8.083c-1.854 0-3.356 1.503-3.356 3.357 0 1.854 1.502 3.356 3.356 3.356 1.854 0 3.357-1.502 3.357-3.356 0-1.854-1.503-3.357-3.357-3.357zm0 5.176c-1.004 0-1.819-.815-1.819-1.819 0-1.004.815-1.819 1.819-1.819 1.004 0 1.819.815 1.819 1.819 0 1.004-.815 1.819-1.819 1.819zM6.924 15.65c-1.258 0-2.278 1.021-2.278 2.279 0 1.258 1.02 2.278 2.278 2.278 1.258 0 2.278-1.02 2.278-2.278 0-1.258-1.02-2.279-2.278-2.279zm0 3.645c-.754 0-1.366-.612-1.366-1.366 0-.754.612-1.366 1.366-1.366.754 0 1.366.612 1.366 1.366 0 .754-.612 1.366-1.366 1.366z"/>
                      </svg>
                      <span class="font-mono tracking-wider">${p.steam_id}</span>
                    </div>
                    ` : ''}
                  </td>
                  <td class="text-center font-semibold text-gray-300">${p.level}</td>
                  <td>
                    <div class="hp-bar-container">
                      <div class="hp-bar-fill" style="width: ${hpPercent}%"></div>
                      <span class="hp-text">${p.hp} / ${p.max_hp} (${Math.round(hpPercent)}%)</span>
                    </div>
                  </td>
                </tr>
              `;
            });
            tbody.innerHTML = html;
          } else {
            statusEl.innerText = 'Main Menu / Not Loaded';
            statusEl.style.color = '#ff9800';
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-gray-500 py-4">Waiting for game load...</td></tr>';
          }
        })
        .catch(err => {
          console.error("Poll error:", err);
          const statusEl = document.getElementById('status-text');
          statusEl.innerText = 'Server Offline (' + err.message + ')';
          statusEl.style.color = '#f44336';
        });
    }

function postAction(type) {
      fetch('/api/action/' + type, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          if(data.message) {
            // Optional: show a nice toast, but for now just alert
            console.log(data.message);
          }
          updateStats();
        })
        .catch(err => console.error("Error communicating with server"));
    }