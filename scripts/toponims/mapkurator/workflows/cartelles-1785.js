// Lectura (OCR-visió) de les 36 CARTEL·LES de poble del mapa original de Despuig
// (1785). Cada agent llegeix UNA vinyeta neta a resolució completa i transcriu la
// cartela de forma ESTRICTAMENT LITERAL, n'extreu les dades factuals i marca dubtes.
// NO se'ls passa el text de la reedició de 1826 (les xifres difereixen i contaminaria).
// Retorna {towns:[...]}; el pare ho desa a data/cartelles-1785/extract.json.
export const meta = {
  name: 'cartelles-1785',
  description: 'Llegeix les 36 cartel·les de poble del mapa de Despuig (1785): transcripció literal + dades factuals',
  phases: [{ title: 'Cartel·les', detail: 'un agent per vinyeta' }],
};

const DIR = '/home/acpicornell/projects/despuig/data/cartelles-1785/crops';
const TOWNS = [
  { slug: 'selva', nom: 'Selva', img: 'despuig-1785-original-selva.jpg' },
  { slug: 'campanet', nom: 'Campanet', img: 'despuig-1785-original-campanet.jpg' },
  { slug: 'lluc', nom: 'Lluc', img: 'despuig-1785-original-lluch.jpg' },
  { slug: 'pollensa', nom: 'Pollença', img: 'despuig-1785-original-pollensa.jpg' },
  { slug: 'alcudia', nom: 'Alcúdia', img: 'fusion_alcudia.jpg' },
  { slug: 'la-puebla', nom: 'sa Pobla (la Puebla)', img: 'despuig-1785-original-sapobla.jpg' },
  { slug: 'muro', nom: 'Muro', img: 'despuig-1785-original-muro.jpg' },
  { slug: 'arta', nom: 'Artà', img: 'despuig-1785-original-arta.jpg' },
  { slug: 'manacor', nom: 'Manacor', img: 'despuig-1785-original-manacor.jpg' },
  { slug: 'petra', nom: 'Petra', img: 'despuig-1785-original-petra.jpg' },
  { slug: 'santa-margarita', nom: 'Santa Margalida', img: 'despuig-1785-original-stamargalida.jpg' },
  { slug: 'sancellas', nom: 'Sencelles', img: 'despuig-1785-original-sencelles.jpg' },
  { slug: 'sineu', nom: 'Sineu', img: 'despuig-1785-original-sineu.jpg' },
  { slug: 'san-juan', nom: 'Sant Joan', img: 'despuig-1785-original-stjoan.jpg' },
  { slug: 'montuiri', nom: 'Montuïri', img: 'despuig-1785-original-montuiri.jpg' },
  { slug: 'porreras', nom: 'Porreres', img: 'despuig-1785-original-porreres.jpg' },
  { slug: 'felanitx', nom: 'Felanitx', img: 'despuig-1785-original-felanitx.jpg' },
  { slug: 'andraitx', nom: 'Andratx', img: 'despuig-1785-original-andratx.jpg' },
  { slug: 'calvia', nom: 'Calvià', img: 'despuig-1785-original-calvia.jpg' },
  { slug: 'santa-maria', nom: 'Santa Maria del Camí', img: 'despuig-1785-original-stamaria.jpg' },
  { slug: 'marratxi', nom: 'Marratxí', img: 'fusion_marratxi.jpg' },
  { slug: 'palma', nom: 'Palma', img: 'despuig-1785-original-palma.jpg' },
  { slug: 'algaida', nom: 'Algaida', img: 'despuig-1785-original-algaida.jpg' },
  { slug: 'llucmayor', nom: 'Llucmajor', img: 'despuig-1785-original-llucmajor.jpg' },
  { slug: 'campos', nom: 'Campos', img: 'despuig-1785-original-campos.jpg' },
  { slug: 'santani', nom: 'Santanyí', img: 'despuig-1785-original-santani.jpg' },
  { slug: 'inca', nom: 'Inca', img: 'despuig-1785-original-inca.jpg' },
  { slug: 'binisalem', nom: 'Binissalem', img: 'despuig-1785-original-binissalem.jpg' },
  { slug: 'soller', nom: 'Sóller', img: 'despuig-1785-original-soller.jpg' },
  { slug: 'alaro', nom: 'Alaró', img: 'despuig-1785-original-alaro.jpg' },
  { slug: 'bunola', nom: 'Bunyola', img: 'despuig-1785-original-bunola.jpg' },
  { slug: 'valldemusa', nom: 'Valldemossa', img: 'despuig-1785-original-valldemossa.jpg' },
  { slug: 'esporlas', nom: 'Esporles', img: 'despuig-1785-original-esporles.jpg' },
  { slug: 'puigpunyent', nom: 'Puigpunyent', img: 'despuig-1785-original-puigpunyent.jpg' },
  { slug: 'banyalbufar', nom: 'Banyalbufar', img: 'despuig-1785-original-banyalbufar.jpg' },
  { slug: 'deia', nom: 'Deià', img: 'despuig-1785-original-deia.jpg' },
];

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    nomGravat: { type: 'string' },
    textOriginal: { type: 'string' },
    veins: { type: ['integer', 'null'] },
    animes: { type: ['integer', 'null'] },
    anyVila: { type: ['integer', 'null'] },
    anyCiutat: { type: ['integer', 'null'] },
    nomMoros: { type: ['string', 'null'] },
    nomAntic: { type: ['string', 'null'] },
    collites: { type: 'array', items: { type: 'string' } },
    fires: { type: ['string', 'null'] },
    llogarets: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          nom: { type: 'string' },
          veins: { type: ['integer', 'null'] },
          animes: { type: ['integer', 'null'] },
        },
        required: ['nom', 'veins', 'animes'],
      },
    },
    dubtes: { type: 'array', items: { type: 'string' } },
  },
  required: ['nomGravat', 'textOriginal', 'veins', 'animes', 'anyVila', 'anyCiutat', 'nomMoros', 'nomAntic', 'collites', 'fires', 'llogarets', 'dubtes'],
};

function prompt(t) {
  return `Ets un transcriptor de cartel·les gravades del mapa original de Mallorca del Cardenal Antoni Despuig (1785). La teva feina és llegir la cartela d'un poble i transcriure-la de forma ESTRICTAMENT LITERAL. Inventar, "corregir", completar o endevinar res és un ERROR GREU: destrueix el valor documental. Una lectura parcial i honesta sempre val més que una de segura però equivocada.

La cartela ve retallada en DUES imatges (les dues meitats del bloc de text, perquè un segell rodó el parteix pel mig). Llegeix-les TOTES DUES a resolució completa amb l'eina Read:
  Columna esquerra: ${DIR}/${t.slug}-L.jpg
  Columna dreta:    ${DIR}/${t.slug}-R.jpg
És la cartela de ${t.nom}, en castellà del segle XVIII. A dalt de cada retall pot quedar un tros del paisatge gravat: ignora'l, transcriu NOMÉS el text.

DISPOSICIÓ (molt important): el text flueix LÍNIA A LÍNIA TRAVESSANT les dues columnes. Cada línia de prosa té la seva meitat esquerra a la imatge -L i la meitat dreta a la imatge -R, A LA MATEIXA ALÇADA. Per reconstruir la prosa: pren la línia 1 de -L i continua-la amb la línia 1 de -R; després línia 2 de -L + línia 2 de -R; i així successivament de dalt a baix. El resultat ha de ser castellà del s. XVIII coherent. (Exemple real: -L "SELVA, llamada por los" + -R "Moros Xilvar es villa des-" → "SELVA, llamada por los Moros Xilvar es villa des[de]".)

REGLES:
- NO usis cap coneixement previ del poble ni cap altra edició del mapa. Llegeix NOMÉS els píxels gravats d'aquesta imatge de 1785. Les dades de reedicions posteriors (1814/1829) són DIFERENTS i no s'han de fer servir.
- Transcriu 'textOriginal' tan literal com puguis, respectant l'ortografia d'època (aceyte, vecinos, almas, Reyno, 9bre, Jayme, abreviatures...). Si una paraula és il·legible, posa-hi [...] i afegeix-ho a 'dubtes'. No reordenis ni modernitzis.
- Extreu les xifres EXACTAMENT com estan gravades:
  · veins = nombre de "vecinos" (enter) o null si no hi consta.
  · animes = nombre d'"almas" (enter) o null si no hi consta (algunes cartel·les de 1785 NOMÉS donen vecinos).
  · anyVila = any en què va ser feta vila (enter) o null.
  · anyCiutat = any del títol de ciutat, si n'hi ha (Alcúdia, Palma) o null.
  · nomMoros = nom "llamado por los Moros ..." tal com es grava, o null.
  · nomAntic = nom antic ("llamada antiguamente ...") o null.
  · collites = llista de productes de la cosecha tal com surten (p. ex. ["aceyte","algarrobas","seda"]).
  · fires = text de la fira si se'n menciona, o null.
  · llogarets = pobles/llogarets veïns esmentats dins la cartela amb les seves xifres ([{nom, veins, animes}]); [] si no n'hi ha.
- nomGravat = el nom del poble tal com apareix en MAJÚSCULES al capçal de la cartela (p. ex. "SELVA", "BINISALEM", "Sta MARGARITA").
- 'dubtes' = llista de lectures incertes (xifres ambigües, lletres tallades, paraules dubtoses). Sigues honest: si un dígit no és clar, digues-ho.
- NO INVENTIS RES. Si un camp no hi és, posa null o llista buida.

Retorna l'objecte estructurat amb tots els camps.`;
}

phase('Cartel·les');
const results = await parallel(
  TOWNS.map((t) => () =>
    agent(prompt(t), { label: t.slug, phase: 'Cartel·les', schema: SCHEMA }).then((r) => ({ slug: t.slug, nom: t.nom, img: t.img, ...(r || {}) })),
  ),
);
const towns = results.filter(Boolean);
const ok = towns.filter((t) => t.textOriginal).length;
log(`llegides ${ok}/${TOWNS.length} cartel·les`);
return { count: towns.length, towns };
