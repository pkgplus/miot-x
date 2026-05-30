function app() {
    return {
        loggedIn: false,
        loginLoading: false,
        loginError: '',
        manualMode: false,
        callbackUrl: '',
        tab: 'devices',
        devices: [],
        scenes: [],
        homes: [],
        selectedHomes: [],
        currentDevice: null,
        propValues: {},
        pollTimer: null,

        async init() {
            await this.checkAuth();
            if (this.loggedIn) await this.loadData();
            document.addEventListener('set-prop', (e) => {
                const { siid, piid, value } = e.detail;
                this.setPropValue(siid, piid, value);
            });
        },

        async checkAuth() {
            try {
                const res = await fetch('/api/auth/status');
                const data = await res.json();
                this.loggedIn = data.logged_in;
            } catch (e) { this.loggedIn = false; }
        },

        async startLogin() {
            this.loginLoading = true;
            this.loginError = '';
            this.manualMode = false;
            try {
                const res = await fetch('/api/auth/start', { method: 'POST' });
                const data = await res.json();
                window.open(data.auth_url, '_blank');
                if (data.auto_callback) {
                    this.pollTimer = setInterval(async () => {
                        await this.checkAuth();
                        if (this.loggedIn) {
                            clearInterval(this.pollTimer);
                            this.loginLoading = false;
                            await this.loadData();
                        }
                    }, 2000);
                    setTimeout(() => {
                        if (!this.loggedIn) {
                            clearInterval(this.pollTimer);
                            this.loginLoading = false;
                            this.manualMode = true;
                        }
                    }, 120000);
                } else {
                    this.loginLoading = false;
                    this.manualMode = true;
                }
            } catch (e) {
                this.loginLoading = false;
                this.loginError = '启动登录失败: ' + e.message;
            }
        },

        async submitCallback() {
            const match = this.callbackUrl.match(/[?&]code=([^&]+)/);
            if (!match) { this.loginError = 'URL 中未找到授权码'; return; }
            try {
                const res = await fetch('/api/auth/callback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: match[1] }),
                });
                const data = await res.json();
                if (data.success) {
                    this.loggedIn = true;
                    this.manualMode = false;
                    await this.loadData();
                } else {
                    this.loginError = data.error || '登录失败';
                }
            } catch (e) { this.loginError = '提交失败: ' + e.message; }
        },

        async logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            this.loggedIn = false;
            this.devices = [];
            this.scenes = [];
            this.homes = [];
            this.currentDevice = null;
        },

        async loadData() {
            await Promise.all([this.loadDevices(), this.loadScenes(), this.loadHomes()]);
        },

        async loadDevices() {
            try {
                const res = await fetch('/api/devices');
                if (!res.ok) return;
                const data = await res.json();
                this.devices = data.devices || [];
            } catch (e) { /* ignore */ }
        },

        async loadScenes() {
            try {
                const res = await fetch('/api/scenes');
                if (!res.ok) return;
                const data = await res.json();
                this.scenes = data.scenes || [];
            } catch (e) { /* ignore */ }
        },

        async loadHomes() {
            try {
                const res = await fetch('/api/homes');
                if (!res.ok) return;
                const data = await res.json();
                this.homes = data.homes || [];
                this.selectedHomes = data.selected || [];
            } catch (e) { /* ignore */ }
        },

        async openDevice(dev) {
            this.currentDevice = { ...dev, spec: null };
            this.propValues = {};
            try {
                const res = await fetch(`/api/devices/${dev.did}`);
                if (!res.ok) return;
                const data = await res.json();
                this.currentDevice = data;
                await this.loadPropValues();
            } catch (e) { /* ignore */ }
        },

        async loadPropValues() {
            if (!this.currentDevice?.spec) return;
            for (const service of this.currentDevice.spec.services) {
                for (const prop of service.properties) {
                    if (prop.access && prop.access.includes('read')) {
                        try {
                            const res = await fetch(`/api/devices/${this.currentDevice.did}/prop/${service.iid}/${prop.iid}`);
                            if (res.ok) {
                                const data = await res.json();
                                this.propValues[`${service.iid}-${prop.iid}`] = data.value;
                            }
                        } catch (e) { /* ignore */ }
                    }
                }
            }
        },

        async toggleProp(siid, piid) {
            const key = `${siid}-${piid}`;
            const newVal = !this.propValues[key];
            this.propValues[key] = newVal;
            await this.setPropValue(siid, piid, newVal);
        },

        async setPropValue(siid, piid, value) {
            const key = `${siid}-${piid}`;
            this.propValues[key] = value;
            try {
                await fetch(`/api/devices/${this.currentDevice.did}/prop`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ siid, piid, value }),
                });
            } catch (e) { /* ignore */ }
        },

        async runScene(sceneId) {
            await fetch(`/api/scenes/${sceneId}/run`, { method: 'POST' });
        },

        async saveHomes() {
            const ids = this.selectedHomes.length > 0 ? this.selectedHomes : null;
            await fetch('/api/homes/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ home_ids: ids }),
            });
            await this.loadData();
        },
    };
}
