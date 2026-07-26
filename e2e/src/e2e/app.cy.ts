import { getGreeting } from '../support/app.po';

describe('who-eats-whom', () => {
  beforeEach(() => cy.visit('/'));

  it('should display the main title', () => {
    getGreeting().contains('Who Eats Whom');
  });

  it('should display the current copyright and iNaturalist attribution', () => {
    const currentYear = new Date().getFullYear();

    cy.get('footer')
      .should('contain.text', `© ${currentYear} Bradley Allf`)
      .within(() => {
        cy.contains('a', 'Powered by')
          .should('have.attr', 'href', 'https://www.inaturalist.org/')
          .find('img[alt="iNaturalist"]')
          .should('be.visible')
          .and(($image) => {
            expect(($image[0] as HTMLImageElement).naturalWidth).to.be.greaterThan(
              0
            );
          });
      });

    cy.get('footer').scrollIntoView().screenshot('footer-attribution');
  });
});
