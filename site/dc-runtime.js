/*
 * dc-runtime.js — renders the QuantEra landing page.
 *
 * The page is authored as a declarative template (#dc-template) plus one
 * component class (#dc-logic). This runtime parses the template once, turns it
 * into React elements on every render, and fills {{ holes }}, <sc-for> loops
 * and <sc-if> conditionals from the component's renderVals().
 * Depends on React 18 and ReactDOM 18 (UMD globals). No build step.
 */
(function () {
  "use strict";
  var VOID = new Set(["input", "meta", "link", "br", "img", "hr", "source", "col", "area", "wbr"]);
  var deco = document.createElement("textarea");
  function decode(s) { if (s.indexOf("&") < 0) return s; deco.innerHTML = s; return deco.value; }

  function parse(html) {
    var root = { tag: "#root", attrs: {}, children: [] };
    var stack = [root];
    var top = function () { return stack[stack.length - 1]; };
    var re = /<!--[\s\S]*?-->|<!doctype[^>]*>|<\/([a-zA-Z][a-zA-Z0-9-]*)\s*>|<([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=>\/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>/gi;
    var m, last = 0;
    while ((m = re.exec(html))) {
      if (m.index > last) top().children.push({ tag: "#text", text: html.slice(last, m.index) });
      last = re.lastIndex;
      if (m[0].charAt(1) === "!") continue;
      if (m[1]) {
        for (var k = stack.length - 1; k > 0; k--) { if (stack[k].tag === m[1]) { stack.length = k; break; } }
        continue;
      }
      var tag = m[2], attrs = {};
      var ar = /([^\s=>\/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g, a;
      while ((a = ar.exec(m[3] || ""))) {
        var raw = a[2] != null ? a[2] : a[3] != null ? a[3] : a[4] != null ? a[4] : "";
        attrs[a[1]] = decode(raw);
      }
      var node = { tag: tag, attrs: attrs, children: [] };
      top().children.push(node);
      if (tag === "script" || tag === "style") {
        var end = html.indexOf("</" + tag, last);
        node.text = html.slice(last, end);
        last = end; re.lastIndex = end;
        continue;
      }
      if (!VOID.has(tag.toLowerCase()) && !m[4]) stack.push(node);
    }
    if (last < html.length) top().children.push({ tag: "#text", text: html.slice(last) });
    return root;
  }

  var HOLE = /\{\{\s*([^}]+?)\s*\}\}/g;
  function lookup(path, scope) {
    path = path.trim();
    if (path === "true") return true;
    if (path === "false") return false;
    if (/^-?\d+(\.\d+)?$/.test(path)) return Number(path);
    var v = scope, parts = path.split(".");
    for (var i = 0; i < parts.length; i++) { if (v == null) return undefined; v = v[parts[i]]; }
    return v;
  }
  function fill(str, scope) { return str.replace(HOLE, function (_, p) { var v = lookup(p, scope); return v == null ? "" : String(v); }); }
  function attrVal(raw, scope) {
    var whole = /^\s*\{\{\s*([^}]+?)\s*\}\}\s*$/.exec(raw);
    return whole ? lookup(whole[1], scope) : fill(raw, scope);
  }
  function camel(s) { return s.replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); }); }
  function styleObj(str) {
    var o = {};
    String(str).split(";").forEach(function (d) {
      var i = d.indexOf(":"); if (i < 0) return;
      var k = d.slice(0, i).trim(), v = d.slice(i + 1).trim(); if (!k) return;
      o[k.indexOf("--") === 0 ? k : camel(k)] = v;
    });
    return o;
  }
  var RENAME = { "class": "className", "for": "htmlFor", spellcheck: "spellCheck", tabindex: "tabIndex", readonly: "readOnly", maxlength: "maxLength", autocomplete: "autoComplete" };

  function build(node, scope, key) {
    var h = React.createElement;
    if (node.tag === "#text") return decode(fill(node.text, scope));
    if (node.tag === "helmet") return null;
    if (node.tag === "sc-for") {
      var list = attrVal(node.attrs.list, scope) || [];
      var as = node.attrs.as || "item";
      return list.map(function (item, idx) {
        var s = Object.assign({}, scope); s[as] = item; s.$index = idx;
        return h(React.Fragment, { key: idx }, kids(node, s));
      });
    }
    if (node.tag === "sc-if") return attrVal(node.attrs.value, scope) ? h(React.Fragment, { key: key }, kids(node, scope)) : null;
    var props = { key: key };
    Object.keys(node.attrs).forEach(function (name) {
      if (name.indexOf("hint-") === 0) return;
      var v = attrVal(node.attrs[name], scope);
      var n = RENAME[name] || name;
      if (n === "style") { props.style = styleObj(v); return; }
      if (n.indexOf("data-") !== 0 && n.indexOf("aria-") !== 0 && n.indexOf("-") > 0) n = camel(n);
      props[n] = v;
    });
    if (node.tag === "textarea" && props.value == null) props.value = "";
    return h.apply(null, [node.tag, props].concat(kids(node, scope)));
  }
  function kids(node, scope) {
    if (node.tag === "textarea") return [];
    return node.children.map(function (c, i) { return build(c, scope, i); });
  }
  function find(n, t) { if (n.tag === t) return n; var c = n.children || []; for (var i = 0; i < c.length; i++) { var r = find(c[i], t); if (r) return r; } return null; }
  function findAll(n, t, out) { out = out || []; if (n.tag === t) out.push(n); (n.children || []).forEach(function (c) { findAll(c, t, out); }); return out; }

  function boot() {
    var tpl = parse(document.getElementById("dc-template").textContent);
    var helmet = find(tpl, "helmet");
    if (helmet) findAll(helmet, "style").forEach(function (s) { var el = document.createElement("style"); el.textContent = s.text; document.head.appendChild(el); });
    var body = tpl.children.filter(function (c) { return c.tag !== "helmet"; });
    function DCLogic(props) { React.Component.call(this, props); }
    DCLogic.prototype = Object.create(React.Component.prototype);
    DCLogic.prototype.constructor = DCLogic;
    DCLogic.prototype.render = function () {
      var vals = this.renderVals();
      return React.createElement.apply(null, [React.Fragment, null].concat(body.map(function (c, i) { return build(c, vals, i); })));
    };
    var Comp = new Function("DCLogic", "React", document.getElementById("dc-logic").textContent + "\n;return Component;")(DCLogic, React);
    var mount = document.getElementById("app");
    ReactDOM.createRoot(mount).render(React.createElement(Comp, { motion: true }));
    document.documentElement.classList.add("dc-ready");
  }
  try { boot(); } catch (e) {
    console.error(e);
    var f = document.getElementById("boot-fallback"); if (f) f.hidden = false;
  }
})();
