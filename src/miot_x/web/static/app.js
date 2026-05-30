function app() {
    return {
        loggedIn: false, loginLoading: false, loginError: '', manualMode: false, callbackUrl: '',
        tab: 'home', currentDevice: null, propValues: {},
        devices: [], scenes: [], homes: [], selectedHomes: [],
        roomFilter: '', typeFilter: '', pollTimer: null,

        get rooms() {
            const r = new Set(this.devices.map(d => d.room).filter(Boolean));
            return [...r];
        },
        get filteredDevices() {
            return this.devices.filter(d => !this.roomFilter || d.room === this.roomFilter);
        },
        get typedDevices() {
            if (!this.typeFilter) return this.devices;
            return this.devices.filter(d => this.getDeviceType(d) === this.typeFilter);
        },

        async init() {
            await this.checkAuth();
            if (this.loggedIn) await this.loadData();
            document.addEventListener('set-prop', e => {
                const { siid, piid, value } = e.detail;
                this.setPropValue(siid, piid, value);
            });
        },

        navigate(t) { this.tab = t; this.currentDevice = null; },

        async checkAuth() {
            try { const r = await fetch('/api/auth/status'); const d = await r.json(); this.loggedIn = d.logged_in; } catch { this.loggedIn = false; }
        },
        async startLogin() {
            this.loginLoading = true; this.loginError = ''; this.manualMode = false;
            try {
                const r = await fetch('/api/auth/start', { method: 'POST' }); const d = await r.json();
                window.open(d.auth_url, '_blank');
                if (d.auto_callback) {
                    this.pollTimer = setInterval(async () => { await this.checkAuth(); if (this.loggedIn) { clearInterval(this.pollTimer); this.loginLoading = false; await this.loadData(); } }, 2000);
                    setTimeout(() => { if (!this.loggedIn) { clearInterval(this.pollTimer); this.loginLoading = false; this.manualMode = true; } }, 120000);
                } else { this.loginLoading = false; this.manualMode = true; }
            } catch (e) { this.loginLoading = false; this.loginError = e.message; }
        },
        async submitCallback() {
            const m = this.callbackUrl.match(/[?&]code=([^&]+)/);
            if (!m) { this.loginError = 'URL 中未找到授权码'; return; }
            try {
                const r = await fetch('/api/auth/callback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: m[1] }) });
                const d = await r.json();
                if (d.success) { this.loggedIn = true; this.manualMode = false; await this.loadData(); }
                else { this.loginError = d.error || '失败'; }
            } catch (e) { this.loginError = e.message; }
        },
        async logout() { await fetch('/api/auth/logout', { method: 'POST' }); this.loggedIn = false; this.devices = []; this.scenes = []; this.homes = []; this.currentDevice = null; },

        async loadData() { await Promise.all([this.loadDevices(), this.loadScenes(), this.loadHomes()]); },
        async loadDevices() {
            try { const r = await fetch('/api/devices'); if (!r.ok) return; const d = await r.json(); this.devices = (d.devices || []).map(dev => ({ ...dev, _on: false })); } catch {}
        },
        async loadScenes() { try { const r = await fetch('/api/scenes'); if (!r.ok) return; const d = await r.json(); this.scenes = d.scenes || []; } catch {} },
        async loadHomes() { try { const r = await fetch('/api/homes'); if (!r.ok) return; const d = await r.json(); this.homes = d.homes || []; this.selectedHomes = d.selected || []; } catch {} },

        async openDevice(dev) {
            this.currentDevice = { ...dev, spec: null }; this.propValues = {};
            try { const r = await fetch(`/api/devices/${dev.did}`); if (!r.ok) return; const d = await r.json(); this.currentDevice = d; await this.loadPropValues(); } catch {}
        },
        async loadPropValues() {
            if (!this.currentDevice?.spec) return;
            const promises = [];
            for (const svc of this.currentDevice.spec.services) {
                for (const prop of svc.properties) {
                    if (prop.access && prop.access.includes('read')) {
                        promises.push(
                            fetch(`/api/devices/${this.currentDevice.did}/prop/${svc.iid}/${prop.iid}`)
                                .then(r => r.ok ? r.json() : null)
                                .then(d => { if (d) this.propValues[`${svc.iid}-${prop.iid}`] = d.value; })
                                .catch(() => {})
                        );
                    }
                }
            }
            await Promise.all(promises);
        },

        async toggleProp(siid, piid) {
            const k = `${siid}-${piid}`; const nv = !this.propValues[k]; this.propValues[k] = nv;
            await this.setPropValue(siid, piid, nv);
        },
        async setPropValue(siid, piid, value) {
            const k = `${siid}-${piid}`; this.propValues[k] = value;
            try { await fetch(`/api/devices/${this.currentDevice.did}/prop`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ siid, piid, value }) }); } catch {}
        },
        async quickToggle(dev) {
            dev._on = !dev._on;
            const action = dev._on ? 'on' : 'off';
            try { await fetch(`/api/devices/${dev.did}/${action}`, { method: 'POST' }); } catch {}
        },
        async runScene(id) { try { await fetch(`/api/scenes/${id}/run`, { method: 'POST' }); } catch {} },
        async saveHomes() {
            const ids = this.selectedHomes.length > 0 ? this.selectedHomes : null;
            await fetch('/api/homes/select', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ home_ids: ids }) });
            await this.loadData();
        },

        // Device type detection
        getDeviceType(dev) {
            if (!dev) return 'default';
            const m = (dev.model || '').toLowerCase();
            const u = (dev.urn || '').toLowerCase();
            if (m.includes('light') || m.includes('lamp') || u.includes(':light:')) return 'light';
            if (m.includes('heater') || m.includes('bath') || m.includes('aircondition') || m.includes('acpartner') || u.includes(':heater:') || u.includes(':air-condition')) return 'climate';
            if (m.includes('sensor') || u.includes(':sensor:') || u.includes(':temperature')) return 'sensor';
            if (m.includes('switch') || m.includes('plug') || m.includes('outlet') || u.includes(':switch:') || u.includes(':outlet:')) return 'switch';
            if (m.includes('camera') || m.includes('chuangmi') || u.includes(':camera:') || u.includes(':video-doorbell')) return 'camera';
            return 'default';
        },
        deviceColor(dev) {
            if (!dev || !dev.online) return 'tile-off';
            return 'tile-' + this.getDeviceType(dev);
        },
        deviceIcon(dev, size) {
            const s = size || 28;
            const type = this.getDeviceType(dev);
            const icons = {
                light: '💡', climate: '🌡️', sensor: '📊', switch: '🔌', camera: '📷', default: '📱'
            };
            return `<span style="font-size:${s}px">${icons[type]}</span>`;
        },
        deviceStatus(dev) {
            if (!dev) return '';
            if (!dev.online) return '离线';
            const type = this.getDeviceType(dev);
            if (type === 'sensor') return '监测中';
            if (type === 'camera') return '在线';
            return dev._on ? '已开启' : '待命';
        },
        isToggleable(dev) {
            const t = this.getDeviceType(dev);
            return t === 'light' || t === 'climate' || t === 'switch' || t === 'default';
        },
    };
}
