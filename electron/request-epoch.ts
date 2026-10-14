// Async work may finish after logout or another authentication request. Its
// result must not revive a session that the user has already replaced.
export class RequestEpoch {
  private value = 0;

  capture() { return this.value; }
  invalidate() { return ++this.value; }
  isCurrent(epoch: number) { return epoch === this.value; }
}
