export function startAuthenticatedApplication({ requireSession, state, boot, toast }) {
  return requireSession()
    .then((user) => {
      if (!user) return;
      state.user = user;
      return boot();
    })
    .catch((error) => toast(error.message, true));
}
