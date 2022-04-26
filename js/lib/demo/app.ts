import express, { Request, Response } from 'express';
import puppeteer from 'puppeteer-core';
import { Logger } from 'winston';
import { ExtractorOptions } from '../extractor';
import { logFile } from '../logging';
import { tryParseInt } from '../utils';
import { loadModel, Model } from './model-info';
import { PageInference } from './page-inference';
import { Inference } from './python';

export class DemoOptions {
  public readonly debug: boolean;
  /** More verbose logging. */
  public readonly port: number;
  /** Log full HTML and visuals to `scraping_logs`. */
  public readonly logInputs: boolean;
  /** Set when developing server UI to avoid waiting for Python. */
  public readonly mockInference: boolean;
  /** Puppeteer page loading timeout in seconds. */
  public readonly timeout: number;
  /** Send artificially large response chunks to bypass network buffering. */
  public readonly largeChunks: number;

  public constructor() {
    this.debug = !!process.env.DEBUG;
    this.port = tryParseInt(process.env.PORT, 3000);
    this.logInputs = !!process.env.LOG_INPUTS;
    this.mockInference = !!process.env.MOCK_INFERENCE;
    this.timeout = tryParseInt(process.env.TIMEOUT, 15);
    this.largeChunks = tryParseInt(process.env.LARGE_CHUNKS, 0);
  }

  public get largeChunk() {
    if (this.largeChunks > 0) {
      return '<!--' + 'x'.repeat(this.largeChunks) + '-->';
    } else {
      return null;
    }
  }
}

export class DemoApp {
  public readonly extractorOptions: ExtractorOptions;
  public readonly python: Inference | null = null;
  public browser: Promise<puppeteer.Browser> | puppeteer.Browser;

  private constructor(
    public readonly options: DemoOptions,
    public readonly log: Logger,
    public readonly model: Model
  ) {
    this.extractorOptions = ExtractorOptions.fromModelParams(model.params);
    this.log.info('extractor options', { options: this.extractorOptions });

    // Create Express HTTP server.
    const app = express();
    app.get('/', this.mainPage);

    // Start the server.
    log.verbose('starting demo server');
    const server = app.listen(options.port, async () => {
      console.log(`Listening on http://localhost:${options.port}/`);
    });

    // Create Puppeteer.
    this.browser = new Promise<puppeteer.Browser>(async (resolve) => {
      log.verbose('opening Puppeteer');
      const browser = await puppeteer.launch({
        args: [
          // Allow running as root.
          '--no-sandbox',
        ],
        executablePath: 'google-chrome-stable',
      });
      log.verbose('opened Puppeteer');
      resolve(browser);
      this.browser = browser;
    });

    if (!options.mockInference) {
      // Start Python inference shell.
      this.python = new Inference(options, log);

      // Close the server when Python closes.
      this.python.shell.on('close', () => {
        log.verbose('closing server');
        setTimeout(() => {
          log.error('closing timeout');
          process.exit(2);
        }, 5000);
        server.close((err) => {
          log.verbose('closed server', { err });
          process.exit(1);
        });
      });
    }
  }

  public static async start(options: DemoOptions, logger: Logger) {
    const log = logger.child({});
    log.info('start', { options, logLevel: log.level, logFile });

    // Load model.
    const model = await loadModel();
    log.verbose('loaded model', {
      versionDir: model.versionDir,
      info: model.info,
    });

    return new DemoApp(options, log, model);
  }

  private mainPage = async (req: Request, res: Response) => {
    const inference = new PageInference(this, req, res);
    try {
      await inference.run();
    } finally {
      await inference.close();
    }
  };
}
