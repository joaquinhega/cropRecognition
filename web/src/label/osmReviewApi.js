import { getJson, sendJson } from "../api.js";

export const fetchOsmReview = () => getJson("/osm-review");

export const fetchReferenceScene = (n) => getJson(`/osm-review/${n}/scene`);

export const saveOsmVerdict = (n, verdict, note) => sendJson("PUT", `/osm-review/${n}`, { verdict, note });
