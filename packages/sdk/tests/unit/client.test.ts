import {
  SpinupMail,
  SpinupMailApiError,
  SpinupMailValidationError,
} from "@/index";

const buildClient = (fetchMock: typeof fetch, organizationId = "org-1") =>
  new SpinupMail({
    baseUrl: "https://api.spinupmail.com/",
    apiKey: "spin_test_key",
    organizationId,
    fetch: fetchMock,
    headers: {
      "x-trace-id": "trace-1",
    },
  });

describe("SpinupMail SDK client", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
    vi.unstubAllGlobals();
  });

  it("injects API key headers for unscoped requests", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: ["spinupmail.dev"],
          default: "spinupmail.dev",
          forcedLocalPartPrefix: null,
          maxReceivedEmailsPerOrganization: 1000,
          maxReceivedEmailsPerAddress: 100,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );
    const client = buildClient(fetchMock);

    const response = await client.domains.get();

    expect(response.default).toBe("spinupmail.dev");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://api.spinupmail.com/api/domains");
    const headers = new Headers(init?.headers);
    expect(headers.get("x-api-key")).toBe("spin_test_key");
    expect(headers.get("x-org-id")).toBeNull();
    expect(headers.get("x-trace-id")).toBe("trace-1");
  });

  it("normalizes repeated trailing slashes in baseUrl without regex matching", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: ["spinupmail.dev"],
          default: "spinupmail.dev",
          forcedLocalPartPrefix: null,
          maxReceivedEmailsPerOrganization: 1000,
          maxReceivedEmailsPerAddress: 100,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );
    const client = new SpinupMail({
      baseUrl: `https://api.spinupmail.com${"/".repeat(512)}`,
      apiKey: "spin_test_key",
      fetch: fetchMock,
    });

    await client.domains.get();

    expect(fetchMock.mock.calls[0]![0]).toBe(
      "https://api.spinupmail.com/api/domains"
    );
  });

  it("fails fast for organization-scoped methods without an organization id", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const client = buildClient(fetchMock, "");

    await expect(client.addresses.list()).rejects.toBeInstanceOf(
      SpinupMailValidationError
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("validates client-side email list constraints before sending requests", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const client = buildClient(fetchMock);

    await expect(
      client.emails.list({
        addressId: "addr-1",
        search: "verify",
        after: "2026-04-11T10:00:00.000Z",
      })
    ).rejects.toMatchObject({
      name: "SpinupMailValidationError",
      source: "request",
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects ambiguous inbox selectors before sending requests", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const client = buildClient(fetchMock);

    await expect(
      client.emails.list({
        address: "sdk@spinupmail.dev",
        addressId: "addr-1",
      })
    ).rejects.toMatchObject({
      name: "SpinupMailValidationError",
      source: "request",
      message: "Exactly one of address or addressId is required.",
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("serializes Date values for after filters", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          address: "sdk@spinupmail.dev",
          addressId: "addr-1",
          items: [],
          page: 1,
          pageSize: 10,
          totalItems: 0,
          totalPages: 1,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );
    const client = buildClient(fetchMock);
    const after = new Date("2026-04-11T10:00:00.000Z");

    await client.emails.list({
      addressId: "addr-1",
      after,
    });

    const [url] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("after=2026-04-11T10%3A00%3A00.000Z");
  });

  it("serializes pagination values for email lists", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          address: "sdk@spinupmail.dev",
          addressId: "addr-1",
          items: [],
          page: 2,
          pageSize: 25,
          totalItems: 0,
          totalPages: 1,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );
    const client = buildClient(fetchMock);

    await client.emails.list({
      addressId: "addr-1",
      page: 2,
      pageSize: 25,
    });

    const [url] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain("page=2");
    expect(String(url)).toContain("pageSize=25");
  });

  it("rejects non-finite and invalid Date timestamp filters", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const client = buildClient(fetchMock);

    await expect(
      client.emails.list({
        addressId: "addr-1",
        after: Number.NaN,
      })
    ).rejects.toMatchObject({
      name: "SpinupMailValidationError",
      source: "request",
      message: "Invalid timestamp: number values must be finite.",
    });

    await expect(
      client.emails.list({
        addressId: "addr-1",
        after: new Date("not-a-date"),
      })
    ).rejects.toMatchObject({
      name: "SpinupMailValidationError",
      source: "request",
      message: "Invalid timestamp: Date values must be valid.",
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps JSON error payloads into SpinupMailApiError", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: "address not found" }), {
        status: 404,
        headers: {
          "content-type": "application/json",
        },
      })
    );
    const client = buildClient(fetchMock);

    await expect(client.addresses.get("missing")).rejects.toEqual(
      expect.objectContaining<Partial<SpinupMailApiError>>({
        name: "SpinupMailApiError",
        status: 404,
        message: "address not found",
      })
    );
  });

  it("rejects unexpected response shapes", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ unexpected: true }), {
        status: 200,
        headers: {
          "content-type": "application/json",
        },
      })
    );
    const client = buildClient(fetchMock);

    await expect(client.domains.get()).rejects.toMatchObject({
      name: "SpinupMailValidationError",
      source: "response",
    });
  });

  it("returns binary wrappers for raw downloads", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response("raw message", {
        status: 200,
        headers: {
          "content-type": "message/rfc822",
          "content-length": "11",
          "content-disposition": 'attachment; filename="email-1.eml"',
        },
      })
    );
    const client = buildClient(fetchMock);

    const file = await client.emails.getRaw("email-1");

    expect(file.filename).toBe("email-1.eml");
    expect(file.contentType).toBe("message/rfc822");
    expect(file.contentLength).toBe(11);
    await expect(file.text()).resolves.toBe("raw message");
  });

  it("treats malformed content-length values as absent", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response("raw message", {
          status: 200,
          headers: {
            "content-type": "message/rfc822",
            "content-length": "-1",
          },
        })
      )
      .mockResolvedValueOnce(
        new Response("raw message", {
          status: 200,
          headers: {
            "content-type": "message/rfc822",
            "content-length": "1.5",
          },
        })
      );
    const client = buildClient(fetchMock);

    const negativeLengthFile = await client.emails.getRaw("email-1");
    const fractionalLengthFile = await client.emails.getRaw("email-2");

    expect(negativeLengthFile.contentLength).toBeNull();
    expect(fractionalLengthFile.contentLength).toBeNull();
  });

  it("parses RFC 5987 and unquoted filenames from content-disposition", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response("raw message", {
          status: 200,
          headers: {
            "content-type": "message/rfc822",
            "content-disposition":
              "attachment; filename*=UTF-8'en'hello%20world.eml",
          },
        })
      )
      .mockResolvedValueOnce(
        new Response("raw message", {
          status: 200,
          headers: {
            "content-type": "message/rfc822",
            "content-disposition": "attachment; filename=plain-name.eml",
          },
        })
      );
    const client = buildClient(fetchMock);

    const utf8File = await client.emails.getRaw("email-1");
    const unquotedFile = await client.emails.getRaw("email-2");

    expect(utf8File.filename).toBe("hello world.eml");
    expect(unquotedFile.filename).toBe("plain-name.eml");
  });

  it("supports class initialization from environment defaults", async () => {
    process.env.SPINUPMAIL_API_KEY = "spin_env_key";
    process.env.SPINUPMAIL_ORG_ID = "org-env";

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          page: 1,
          pageSize: 10,
          totalItems: 0,
          addressLimit: 100,
          totalPages: 1,
          sortBy: "createdAt",
          sortDirection: "desc",
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );

    const spinupmail = new SpinupMail({ fetch: fetchMock });

    await spinupmail.addresses.list();

    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);

    expect(url).toBe("https://api.spinupmail.com/api/email-addresses");
    expect(headers.get("x-api-key")).toBe("spin_env_key");
    expect(headers.get("x-org-id")).toBe("org-env");
  });

  it("accepts a bare API key string in the SpinupMail constructor", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: ["spinupmail.dev"],
          default: "spinupmail.dev",
          forcedLocalPartPrefix: null,
          maxReceivedEmailsPerOrganization: 1000,
          maxReceivedEmailsPerAddress: 100,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );

    const spinupmail = new SpinupMail("spin_override");
    const domains = new SpinupMail({
      apiKey: "spin_override",
      fetch: fetchMock,
    });

    expect(spinupmail).toBeInstanceOf(SpinupMail);
    await domains.domains.get();

    const [, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(headers.get("x-api-key")).toBe("spin_override");
  });

  it("generates a random localPart when create payload omits it", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "addr-1",
          address: "sum-abc123def456@spinupmail.dev",
          localPart: "sum-abc123def456",
          domain: "spinupmail.dev",
          meta: {},
          integrations: [],
          emailCount: 0,
          allowedFromDomains: [],
          blockedSenderDomains: [],
          inboundRatePolicy: null,
          maxReceivedEmailCount: 100,
          maxReceivedEmailAction: "cleanAll",
          createdAt: "2026-04-11T12:00:00.000Z",
          createdAtMs: 1775908800000,
          expiresAt: null,
          expiresAtMs: null,
          lastReceivedAt: null,
          lastReceivedAtMs: null,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );
    const client = buildClient(fetchMock);

    await client.addresses.create({
      acceptedRiskNotice: true,
    });

    const [, init] = fetchMock.mock.calls[0]!;
    const body = JSON.parse(String(init?.body)) as {
      localPart: string;
      acceptedRiskNotice: boolean;
    };

    expect(body.acceptedRiskNotice).toBe(true);
    expect(body.localPart).toMatch(/^sum-[a-z0-9]{12}$/);
  });

  it("rejects out-of-range random bytes when generating localPart suffixes", async () => {
    const randomByteChunks = [
      [252, 253, 254, 255, 0, 7, 14, 21, 28, 35, 42, 49],
      [245, 246, 247, 251],
    ];
    const getRandomValues = vi.fn((array: Uint8Array) => {
      const chunk = randomByteChunks.shift() ?? [0];
      array.forEach((_, index) => {
        array[index] = chunk[index] ?? 0;
      });
      return array;
    });
    vi.stubGlobal("crypto", { getRandomValues });
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "addr-1",
          address: "sum-abcdefgh9999@spinupmail.dev",
          localPart: "sum-abcdefgh9999",
          domain: "spinupmail.dev",
          meta: {},
          integrations: [],
          emailCount: 0,
          allowedFromDomains: [],
          blockedSenderDomains: [],
          inboundRatePolicy: null,
          maxReceivedEmailCount: 100,
          maxReceivedEmailAction: "cleanAll",
          createdAt: "2026-04-11T12:00:00.000Z",
          createdAtMs: 1775908800000,
          expiresAt: null,
          expiresAtMs: null,
          lastReceivedAt: null,
          lastReceivedAtMs: null,
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        }
      )
    );
    const client = buildClient(fetchMock);

    await client.addresses.create({
      acceptedRiskNotice: true,
    });

    const [, init] = fetchMock.mock.calls[0]!;
    const body = JSON.parse(String(init?.body)) as {
      localPart: string;
    };

    expect(body.localPart).toBe("sum-ahov29gn3459");
    expect(getRandomValues).toHaveBeenCalledTimes(2);
  });

  it("exposes integration management endpoints", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "int-1",
                provider: "telegram",
                name: "Alerts",
                status: "active",
                supportedEventTypes: ["email.received"],
                mailboxCount: 1,
                lastValidatedAt: "2026-04-24T10:00:00.000Z",
                lastValidatedAtMs: 1777024800000,
                createdAt: "2026-04-24T10:00:00.000Z",
                createdAtMs: 1777024800000,
                updatedAt: "2026-04-24T10:00:00.000Z",
                updatedAtMs: 1777024800000,
                publicConfig: {
                  telegramBotId: "123456",
                  botUsername: "spinupmail_bot",
                  chatId: "-1001234567890",
                  chatLabel: "Alerts",
                },
              },
            ],
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [],
            page: 2,
            pageSize: 10,
            totalItems: 0,
            totalPages: 1,
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "dispatch-1",
            status: "pending",
            replayed: true,
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          }
        )
      );
    const client = buildClient(fetchMock);

    const integrations = await client.integrations.list();
    const dispatches = await client.integrations.listDispatches(
      integrations.items[0]!.id,
      {
        page: 2,
        pageSize: 10,
      }
    );
    const replay = await client.integrations.replayDispatch(
      integrations.items[0]!.id,
      "dispatch-1"
    );

    expect(integrations.items[0]!.name).toBe("Alerts");
    expect(dispatches.page).toBe(2);
    expect(replay.replayed).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "https://api.spinupmail.com/api/integrations"
    );
    expect(fetchMock.mock.calls[1]![0]).toBe(
      "https://api.spinupmail.com/api/integrations/int-1/dispatches?page=2&pageSize=10"
    );
    expect(fetchMock.mock.calls[2]![0]).toBe(
      "https://api.spinupmail.com/api/integrations/int-1/dispatches/dispatch-1/replay"
    );
    expect(
      new Headers(fetchMock.mock.calls[0]![1]?.headers).get("x-org-id")
    ).toBe("org-1");
  });

  it("validates integration payloads before sending requests", () => {
    const fetchMock = vi.fn<typeof fetch>();
    const client = buildClient(fetchMock);

    expect(() =>
      client.integrations.create({
        provider: "telegram",
        name: "Alerts",
        config: {
          botToken: "invalid",
          chatId: "-1001234567890",
        },
      })
    ).toThrow(SpinupMailValidationError);

    try {
      client.integrations.create({
        provider: "telegram",
        name: "Alerts",
        config: {
          botToken: "invalid",
          chatId: "-1001234567890",
        },
      });
    } catch (error) {
      expect(error).toMatchObject({
        name: "SpinupMailValidationError",
        source: "request",
      });
    }

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
