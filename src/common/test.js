// Making our own simple variable. Const means we're making a var. lizard is the var name. 
export const lizard = "zooey" // string i.e. character
export const favoriteNumber = 13 // number
export const favoriteNumberString = "13" // string, i.e. character
export const favoriteNumberBoolean = false // in JS t/f are in lowercase. Boolean.
export const someArray = [4, "harryPotter", false, 3] // an array is a collection of things. like a matrix
export const someObject = {
    id: "slytherin", 
    "can": true,
    key:"value"
} // objects are composed of keys and values
// string, boolean, array, object, etc. these are all the types of variables. const = constant variable

console.log(someObject.id) // expected value is slytherin. This is how to access an id.
console.log(someArray[0]) // expected value is 4. Because that's the first thing in someArray
console.log(someArray[1]) // expected value is "harryPotter"

// double quotes and single quotes are same in JS
// export makes it available to other files (i.e. files besides this one)

// Now it's time to make a simple function (some Func)
export const someFunc = (color) => {
    const chimpanzee = "stargaze" // you can also create variables inside functions
    return color 
}
