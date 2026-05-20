// auth.js — 全局认证助手
(function(){
  'use strict';
  var TOKEN_KEY = 'nian_token';
  var USER_KEY  = 'nian_user';
  var MID_KEY   = 'nian_active_memorial';

  window.NianAuth = {
    getToken: function(){ return localStorage.getItem(TOKEN_KEY) || ''; },
    setToken: function(t){ if(t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); },
    getUser:  function(){ try{ return JSON.parse(localStorage.getItem(USER_KEY)||'null'); }catch(e){ return null; } },
    setUser:  function(u){ if(u) localStorage.setItem(USER_KEY, JSON.stringify(u)); else localStorage.removeItem(USER_KEY); },
    getActiveMemorialId: function(){ return localStorage.getItem(MID_KEY) || ''; },
    setActiveMemorialId: function(id){ if(id) localStorage.setItem(MID_KEY, id); else localStorage.removeItem(MID_KEY); },
    isAuthed: function(){ return !!this.getToken(); },
    logout: function(){
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(MID_KEY);
      location.href = '/static/login.html';
    },
    /** fetch 包装：自动加 Authorization，401 自动跳登录 */
    fetch: function(url, opts){
      opts = opts || {};
      opts.headers = opts.headers || {};
      var tok = this.getToken();
      if (tok) opts.headers['Authorization'] = 'Bearer ' + tok;
      var self = this;
      return fetch(url, opts).then(function(r){
        if (r.status === 401) {
          self.logout();
          throw new Error('未登录');
        }
        return r;
      });
    },
    requireAuth: function(){
      if (!this.isAuthed()) { location.href = '/static/login.html'; return false; }
      return true;
    }
  };
})();
