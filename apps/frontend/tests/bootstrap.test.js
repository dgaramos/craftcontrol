import { jest } from "@jest/globals";
import { startAuthenticatedApplication } from "../static/js/features/auth/bootstrap.js";

describe("startAuthenticatedApplication", () => {
  test("sets state.user and calls boot when user is returned", async () => {
    const state = { user: null };
    const user = { name: "Admin", role: "owner" };
    const requireSession = jest.fn().mockResolvedValue(user);
    const boot = jest.fn().mockResolvedValue(undefined);
    const toast = jest.fn();

    await startAuthenticatedApplication({ requireSession, state, boot, toast });

    expect(state.user).toBe(user);
    expect(boot).toHaveBeenCalledTimes(1);
    expect(toast).not.toHaveBeenCalled();
  });

  test("does not call boot when user is null", async () => {
    const state = { user: null };
    const requireSession = jest.fn().mockResolvedValue(null);
    const boot = jest.fn();
    const toast = jest.fn();

    await startAuthenticatedApplication({ requireSession, state, boot, toast });

    expect(boot).not.toHaveBeenCalled();
    expect(state.user).toBeNull();
  });

  test("calls toast with error message on rejection", async () => {
    const state = { user: null };
    const requireSession = jest.fn().mockRejectedValue(new Error("Network error"));
    const boot = jest.fn();
    const toast = jest.fn();

    await startAuthenticatedApplication({ requireSession, state, boot, toast });

    expect(toast).toHaveBeenCalledWith("Network error", true);
    expect(boot).not.toHaveBeenCalled();
  });

  test("propagates boot return value", async () => {
    const state = { user: null };
    const user = { name: "Admin" };
    const requireSession = jest.fn().mockResolvedValue(user);
    const boot = jest.fn().mockResolvedValue("done");
    const toast = jest.fn();

    const result = await startAuthenticatedApplication({ requireSession, state, boot, toast });

    expect(result).toBe("done");
  });
});
