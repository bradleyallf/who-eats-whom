describe('Cypress', () => {
  it('opens the app', () => {
    cy.visit('/');
    cy.contains('Hello Edify').should('be.visible');
  });
});
