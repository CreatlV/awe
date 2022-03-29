import * as cheerio from 'cheerio';
import {
  isComment,
  isDirective,
  isDocument,
  isTag,
  isText,
  Text,
} from 'domhandler';
import { readFile, writeFile } from 'fs/promises';
import h from 'html-template-tag';
import { Logger } from 'winston';
import { DomData, NodeData } from './extractor';
import { PageRecipe } from './page-recipe';

type Node = cheerio.Cheerio<cheerio.NodeWithChildren>;

/** Can blend JSON with visuals (generated by `Extractor`) and original HTML of
 * the page (as seen by the browser, simulated by `cheerio`) into one XML.
 *
 * Thanks to this, visuals should always match HTML DOM, unlike previously when
 * Python HTML parser would parse the DOM differently then Puppeteer visuals
 * extractor, leading to inconsistencies. This happened mainly when HTML was
 * broken.
 *
 * Furthermore, can also load labels, so Python does not have to evaluate CSS
 * selectors (as the used HTML parser Lexbor has some problems with them).
 */
export class Blender {
  private data: DomData = { timestamp: null };
  private dom: cheerio.CheerioAPI = cheerio.load('');
  private result: cheerio.CheerioAPI = cheerio.load('', { xml: true });

  public constructor(
    public readonly recipe: PageRecipe,
    private readonly logger: Logger
  ) {}

  public async loadJsonData() {
    const json = await readFile(this.recipe.jsonPath, { encoding: 'utf-8' });
    this.data = JSON.parse(json);
  }

  public loadHtmlDom() {
    this.dom = cheerio.load(this.recipe.page.html);
    this.dom.prototype.element = function (this: Node) {
      return this[0];
    };
  }

  public blend() {
    this.blendNode(this.data, this.dom.root(), this.result.root(), '/');
  }

  public async save() {
    this.logger.verbose('xml', { path: this.recipe.xmlPath });
    const xml = this.result.xml();
    await writeFile(this.recipe.xmlPath, xml, { encoding: 'utf-8' });
  }

  private blendNode(
    data: NodeData | DomData,
    htmlNode: cheerio.Cheerio<cheerio.NodeWithChildren | Text>,
    xmlNode: Node,
    xpath: string
  ) {
    const log = this.logger.child({ xpath });
    const dataEntries = Object.entries(data);

    // Handle all visual attributes on this JSON level.
    while (dataEntries.length !== 0 && !dataEntries[0][0].startsWith('/')) {
      const [key, value] = dataEntries.shift()!;
      // Ignore some duplicate ones.
      if (key === 'whiteSpace' || key === 'id') continue;
      xmlNode.attr(`_${key}`, value);
    }

    // Only children should be on this JSON level now.
    for (const [key, _] of dataEntries) {
      if (!key.startsWith('/')) {
        log.warn('unexpected key without slash', { key });
        return;
      }
    }

    // Handle all HTML attributes.
    const htmlEl = htmlNode[0];
    if (isText(htmlEl)) {
      xmlNode.attr('_text', htmlEl.data);
    } else if (isTag(htmlEl)) {
      for (const [name, value] of Object.entries(htmlEl.attribs)) {
        const key = name.startsWith('_') ? `__${name}` : name;
        xmlNode.attr(key, value);
      }
    } else if (!isDocument(htmlEl)) {
      log.warn('unrecognized element', { type: htmlEl.type });
      return;
    }

    // Handle all children in both JSON and HTML in parallel.
    const htmlCounts: Map<string, number> = new Map();
    const htmlChildren = isText(htmlEl) ? [] : htmlEl.children;
    while (true) {
      const anyJson = dataEntries.length !== 0;
      const anyHtml = htmlChildren.length !== 0;

      // Inconsistent count of children.
      if (anyJson !== anyHtml) {
        log.warn('unexpected end', { anyJson, anyHtml });
        break;
      }

      // End of children.
      if (!anyJson) break;

      // Get HTML tag name.
      const htmlChild = htmlChildren.shift()!;
      let htmlTagName: string;
      if (isText(htmlChild)) htmlTagName = 'text()';
      else if (isTag(htmlChild)) htmlTagName = htmlChild.tagName;
      else {
        if (!isDirective(htmlChild) && !isComment(htmlChild))
          log.warn('unrecognized child', { type: htmlChild.type });
        continue;
      }
      const htmlTagNum = (htmlCounts.get(htmlTagName) ?? 0) + 1;
      htmlCounts.set(htmlTagName, htmlTagNum);

      // Find corresponding JSON child.
      const xpathElementBare = `/${htmlTagName}`;
      const xpathElement = `${xpathElementBare}[${htmlTagNum}]`;
      const dataEntryIndex = dataEntries.findIndex(
        ([key, _]) => key === xpathElementBare || key === xpathElement
      );
      if (dataEntryIndex < 0) {
        log.warn('non-existent child', { xpathElement });
        continue;
      }
      const [jsonKey, jsonValue] = dataEntries.splice(dataEntryIndex, 1)[0];

      // Create XML node.
      const tagName = htmlTagName === 'text()' ? 'text' : htmlTagName;
      const xmlChild = this.result<cheerio.NodeWithChildren, string>(
        h`<${tagName}>`
      );
      xmlChild.appendTo(xmlNode);

      // Recurse.
      this.blendNode(
        jsonValue as NodeData,
        this.dom(htmlChild),
        xmlChild,
        xpath === '/' ? jsonKey : xpath + jsonKey
      );
    }
  }
}
